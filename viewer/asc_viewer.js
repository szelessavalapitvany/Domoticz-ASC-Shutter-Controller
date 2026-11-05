// ASC viewer: asynchronous, shared device inventory and bounded graph requests. | ASC megjelenítő: aszinkron, közös eszközlista és korlátozott számú párhuzamos grafikonlekérés.
const hardwareReq = '/json.htm?type=command&param=gethardware';
const devicesReq = '/json.htm?type=command&param=getdevices';
const tempReq = '/json.htm?type=command&param=graph&sensor=temp&range=day&idx=';
const switchReq = '/json.htm?type=command&param=getlightlog&range=day&idx=';
const PercentageReq = '/json.htm?type=command&param=graph&sensor=Percentage&range=day&idx=';
const utilityReq = '/json.htm?type=command&param=graph&sensor=counter&range=day&idx=';
const windReq = '/json.htm?type=command&param=graph&sensor=wind&range=day&idx=';

if (typeof window.Redony === 'undefined') { window.Redony = class Redony { constructor() { this.historic = undefined; this.isDimmer = false; } }; }
if (typeof window.RedonyKontroller === 'undefined') { window.RedonyKontroller = class RedonyKontroller { constructor() { this.name = ''; } }; }

function getRequestParam(name) { return new URLSearchParams(window.location.search || (window.location.hash.split('?')[1] || '')).get(name) || undefined; }
function graphResult(response) { return response && Array.isArray(response.result) ? response.result : []; }
function ascEnabled(value) { return value === true || value === 1 || /^(1|true|yes|on|enabled)$/i.test(String(value == null ? '' : value).trim()); }
function ascString(value) { return String(value == null ? '' : value); }
function ascDeviceValue(device) { return device && (device.Data != null ? device.Data : (device.sValue != null ? device.sValue : '')); }
async function ascFetch(url) { const response = await fetch(url, {credentials:'same-origin', signal:AbortSignal.timeout(15000)}); if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`); const data = await response.json(); if (data && data.status && data.status !== 'OK') throw new Error(`Domoticz ${data.status}: ${url}`); return data; }

// Run requests with limited concurrency so a busy Domoticz server stays responsive. | Korlátozott párhuzamosság, hogy a Domoticz szerver terhelhető maradjon.
async function ascRunLimited(jobs, concurrency = 6) {
	let cursor = 0;
	const workers = Array.from({length:Math.min(concurrency,jobs.length)}, async () => {
		while (cursor < jobs.length) {
			const index = cursor++;
			try { await jobs[index](); } catch (error) { console.warn('ASC graph request failed | ASC grafikonlekérés sikertelen:', error); }
		}
	});
	await Promise.all(workers);
}

async function getRedony() {
	window.nodata = true;
	// Fetch the hardware and device lists once, in parallel. | A hardver- és eszközlistát egyszer, párhuzamosan kérjük le.
	const [hardwareResponse, deviceResponse] = await Promise.all([ascFetch(hardwareReq), ascFetch(devicesReq)]);
	const hardwareRows = graphResult(hardwareResponse);
	const hardware = hardwareRows.filter(h => ascString(h.Extra).trim().toUpperCase() === 'ASC' && ascEnabled(h.Enabled));
	const devices = graphResult(deviceResponse);
	console.info('ASC hardware discovery | ASC hardverfelismerés:', {total:hardwareRows.length, asc:hardwareRows.filter(h => ascString(h.Extra).trim().toUpperCase() === 'ASC').length, active:hardware.length});
	if (hardware.length === 0) {
		console.warn('ASC hardware not selected | ASC hardver nem került kiválasztásra:', hardwareRows.map(h => ({idx:h.idx, Name:h.Name, Extra:h.Extra, Enabled:h.Enabled, Type:h.Type})));
		if (!hardwareRows.length) console.error('gethardware result is empty or unexpected | A gethardware válasza üres vagy nem várt szerkezetű:', hardwareResponse);
	}
	window.nodata = hardware.length === 0;
	const byHardware = new Map();
	for (const device of devices) { const id = ascString(device.HardwareID); if (!byHardware.has(id)) byHardware.set(id, new Map()); byHardware.get(id).set(Number(device.Unit), device); }
	const asChoice = d => `${ascString(d.Name)}:${ascString(d.idx)}`;
	const tempnameakt = devices.filter(d => ascString(d.Type).toLowerCase().includes('temp') && (d.Used === 1 || d.Used === '1' || d.Used === true) && /dummy|zigbee/i.test(ascString(d.HardwareName))).map(asChoice);
	const switchnameakt = devices.filter(d => /blind/i.test(ascString(d.SwitchType))).map(asChoice);
	const luxnameakt = devices.filter(d => /lux/i.test(ascString(d.Type)) && ascString(d.HardwareTypeVal) === '15').map(asChoice);
	const windnameakt = devices.filter(d => /wind/i.test(ascString(d.Type)) && ascString(d.HardwareTypeVal) === '15').map(asChoice);
	const vibnameakt = devices.filter(d => d.SwitchType != null && /vibration/i.test(ascString(d.Name))).map(asChoice);
	const jobs = [];
	const redonyok = hardware.map(h => {
		const redony = new window.Redony();
		redony.name = h.Name;
		redony.id = h.idx;
		redony.host = h.Address;
		redony.uname = h.Username;
		redony.pass = h.Password;
		redony.port = h.Port;
		for (let mode = 1; mode <= 6; mode++) redony['Mode'+mode] = ascString(h['Mode'+mode]);
		redony.tempnameakt = tempnameakt;
		redony.switchnameakt = switchnameakt;
		redony.luxnameakt = luxnameakt;
		redony.windnameakt = windnameakt;
		redony.vibnameakt = vibnameakt;
		const units = byHardware.get(ascString(h.idx)) || new Map();
		const get = unit => units.get(unit);
		redony.temptargetminakt = ascDeviceValue(get(3));
		redony.temptargetmaxakt = ascDeviceValue(get(4));
		redony.tempinakt = ascDeviceValue(get(6));
		redony.tempoutakt = ascDeviceValue(get(5));
		redony.luxtakt = parseFloat(ascDeviceValue(get(7))) || 0;
		redony.nyitluxakt = parseFloat(ascDeviceValue(get(16))) || 0;
		redony.erosluxakt = parseFloat(ascDeviceValue(get(17))) || 0;
		redony.windakt = ascDeviceValue(get(18));
		redony.vibrationakt = ascDeviceValue(get(20));
		redony.kapcsoloakt = ascDeviceValue(get(2));
		for (const [unit, field, endpoint] of [
			[6,'tempIn',tempReq],[5,'tempOut',tempReq],[7,'Lux',utilityReq],
			[16,'nyitlux',utilityReq],[17,'eroslux',utilityReq],[18,'wind',windReq],
			[20,'vibration',switchReq],[2,'redonykapcs',PercentageReq]
		]) {
			redony[field] = [];
			const device = get(unit);
			if (!device || !device.idx) continue;
			jobs.push(async () => {
				const records = graphResult(await ascFetch(endpoint + encodeURIComponent(device.idx)));
				if (field === 'vibration') {
					const now = new Date(); const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
					redony[field] = records.filter(item => ascString(item.Date).startsWith(today));
				} else redony[field] = records;
			});
		}
		return redony;
	});
	await ascRunLimited(jobs, 6);
	return redonyok;
}
