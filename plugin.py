"""
Redöny Vezerlo python plugin for Domoticz
Author: szelessav, https://www.szelessavmuhely.hu/hu/redony_vezerles
Version: 1.3.1 (2026-10-17)
"""
"""
<plugin key="ASC" name="ASC (Automatic Shutter Controller) / Redöny vezérlő" author="szelessav" version="1.3.1" externallink="https://www.szelessavmuhely.hu/hu/redony_vezerles">
	<description>
	<h2>ASC (Automatic Shutter Controller)</h2><br/>
	<br/>
	<h3>Setup and configuration: | Beállítás és konfigurálás: </h3>
	<br/>
	<strong><a href="#/Custom/ASC_Shutter_Redony">HTML setup!</a></strong> (Only for existing modules! / Csak már létező modulhoz!)
	<br/>
	<br/>
	<h4>Value parameters | Értékparaméterek:</h4><br/>
	<b>It's colder outside than inside. | Hidegebb van kint mint mint bent.</b><br/>
	<b>1. </b>-- Lux is less than the opening limit (in fact, there is) | -- Lux kisebb mint nyitási limit (sőtét van) <br/>
	<b>2. </b>-- Lux is greater than opening light but less than bright light (normal light) | -- Lux nagyobb mint nyitási de kisebb mint erős fény (normál fény) <br/>
	<b>3. </b>-- Lux greater than strong light (strong sunshine) | -- Lux nagyobb mint erős fény (erős napsütés) <br/>
	<b>4. </b>-- 1. + presence | -- 1. + jelenlét <br/>
	<b>5. </b>-- 2. + presence | -- 2. + jelenlét <br/>
	<b>6. </b>-- 3. + presence | -- 3. + jelenlét. <br/><br/>
	<b>It's warmer outside than inside | Melegebb van kint mint mint bent </b><br/>
	<b>7. </b>-- Lux is less than the opening limit (in fact, there is) | -- Lux kisebb mint nyitási limit (sőtét van) <br/>
	<b>8. </b>-- Lux is greater than opening light but less than bright light (normal light) | -- Lux nagyobb mint nyitási de kisebb mint erős fény (normál fény) <br/>
	<b>9. </b>-- Lux greater than strong light (strong sunshine) | -- Lux nagyobb mint erős fény (erős napsütés) <br/>
	<b>10. </b>-- 7. + presence | -- 7. + jelenlét <br/>
	<b>11 .</b>-- 8. + presence | -- 8. + jelenlét <br/>
	<b>12. </b>-- 9. + presence | -- 9. + jelenlét<br/><br/><br/>
	</description>
	<params>
		<param field="Address" label="Domoticz IP Address" width="200px" required="true" default="127.0.0.1"/>

		<param field="Port" label="Port" width="40px" required="true" default="8080"/>

		<param field="Username" label="Username" width="200px" required="false" default=""/>

		<param field="Password" label="Password" width="200px" required="false" default=""/>

		<param field="Mode1" label="External temperature sensor = K:idx, Internal temperature sensor = B:idx, Light sensor = F:idx, Wind speed sensor = S:idx, Vibration sensor = V:idx" width="400px" required="false" default=""/>

		<param field="Mode2" label="Shutter switch(s) (csv list of idx)" width="100px" required="false" default=""/>

		<param field="Mode3" label="If the internal temperature is lower than the target min. (0,0,100,0,100,100,100,100,100,100,100,100)" width="250px" required="true" default="0,0,100,0,100,100,100,100,100,100,100,100"/>

		<param field="Mode4" label="If the internal temperature is between target min and target max. (0,0,0,0,100,100,0,0,0,20,100,80)" width="250px" required="true" default="0,0,0,0,100,100,0,0,0,20,100,80"/>

		<param field="Mode5" label="If the internal temperature is higher than the target max. (100,100,100,100,100,100,50,50,10,50,50,50)" width="250px" required="true" default="100,100,100,100,100,100,50,50,10,50,50,50"/>

		<param field="Mode6" label="Logging Level (Python Only =2, Basic =62, All =1, None =0), Update cycle, presence detection name (default: 0,5,Phone)" width="250px" required="true" default="0,5,Telefon"/>
	</params>
	
</plugin>
"""
import Domoticz
import json
from urllib import parse, request
from datetime import datetime, timedelta
import time
import math
import base64
import itertools
import re
import os
import heapq

class deviceparam:

	def __init__(self, unit, nvalue, svalue):
		self.unit = unit
		self.nvalue = nvalue
		self.svalue = svalue

class switchparam:

	def __init__(self, idx, command):
		self.idx = idx
		self.command = command

class TranslationLoader:

	def __init__(self, language="en"):
		self.translations = self.load_translations(language)
		if not self.translations:
			Domoticz.Debug("Error loading translations | Hiba a fordítások betöltésekor!")
			self.translations = self.load_translations("en") 

	def load_translations(self, language):
		file_path = os.path.join(Parameters["HomeFolder"], f'asc_translate_{language}.json')
		try:
			with open(file_path, 'r', encoding='utf-8') as file:
				return json.load(file)
		except (FileNotFoundError, json.JSONDecodeError) as e:
			Domoticz.Debug(f"Cannot load translation file | Fordítási fájl nem olvasható: '{file_path}': {e}")
			return {} 

	def t(self, text):
		return self.translations.get(text, text)  # If there is no translation, it returns with the original text


class BasePlugin:

	def __init__(self):

		self.debug = True
		self.ActiveSensors = {}
		self._fav_actions = {}
		self.OutTempSensors = []
		self.InTempSensors = []
		self.intemp = 22.0
		self.lastintemp = 20.0
		self.intemplist = []
		self.outtemp = 20.0
		self.lastouttemp = 20.0
		self.outtemplist = []
		self.targettempmin = 23.0
		self.targettempmax = 24.0
		self.FenySensor = []
		self.WindSensor = []
		self.VibrationSensor = []
		self.lux = 100.0
		self.aktlux = 100.0
		self.lastlux = 100.0
		self.Redony = []
		self.jelenlet = None
		self.jelenletInfo = None
		self.lastjelenletInfo = None
		self.loglevel = None
		self.statussupported = True
		self.nextupdate = datetime.now()
		self.nextjelenlet = datetime.now()
		self.nextchek = datetime.now()
		self.lastpercent = None
		self.nextupdatetime = None
		self.nyitlux = 0.0
		self.eroslux = 1500.0
		self.hiszterezis = 1.0
		listlux = []
		self.current_hour = datetime.now().hour
		self.now_outtemp = 20.0
		self.now_lux = None
		self.now_rain = 0.0
		self.now_wind = 0.0
		self.min_lux = 0
		self.max_lux = 1500
		self.lastday = 5
		self.wind_limit = 0
		self.vibration_limit = None
		self.last_wind_limit = False
		self.last_vibration = None
		self.aktvibration = False
		self.wind = 0
		self.lux_hiszterezis = 1
		self.luxhiszterezis = 10
		self.met_data_string = None
		self.luxhistory = []
		self.location = []
		self.vibration_time_limit = 0
		return


	def onStart(self):

		self.location = Settings.get("Location", "").split(";")
		
		self.tl = TranslationLoader(Parameters["Language"])

		paramslist = parseCSVparamslist(Parameters["Mode6"])
		self.debuglevel = paramslist[0] if paramslist else 0
		
		self.nextupdatetime = paramslist[1] if len(paramslist) > 1 else 5

		if self.nextupdatetime < 0:
			self.nextupdatetime = 0

		if len(paramslist) > 2:
			self.jelenlet = paramslist[2]

		# Configure log level | loggolási szint beállítása
		try:
			debuglevel = self.debuglevel
		except ValueError:
			debuglevel = 0
			self.loglevel = "None"
		if debuglevel != 0:
			self.debug = True
			Domoticz.Debugging(debuglevel)
			DumpConfigToLog()
			self.loglevel = "Verbose"
		else:
			self.debug = False
			Domoticz.Debugging(0)

		# Parse configuration parameters | paraméterek szétbontása
		hideg = parseCSV(Parameters["Mode3"])
		
		Domoticz.Debug("Cold parameter count | Hideg paraméterek száma = "+format(len(hideg)))
		if len(hideg) >= 12 :
			self.H1 = hideg[0]
			Domoticz.Debug(("self.H1 = "+format(self.H1)) + ' | Mért vagy számított érték')
			self.H2 = hideg[1]
			Domoticz.Debug(("self.H2 = "+format(self.H2)) + ' | Mért vagy számított érték')
			self.H3 = hideg[2]
			Domoticz.Debug(("self.H3 = "+format(self.H3)) + ' | Mért vagy számított érték')
			self.H4 = hideg[3]
			Domoticz.Debug(("self.H4 = "+format(self.H4)) + ' | Mért vagy számított érték')
			self.H5 = hideg[4]
			Domoticz.Debug(("self.H5 = "+format(self.H5)) + ' | Mért vagy számított érték')
			self.H6 = hideg[5]
			Domoticz.Debug(("self.H6 = "+format(self.H6)) + ' | Mért vagy számított érték')
			self.H7 = hideg[6]
			Domoticz.Debug(("self.H7 = "+format(self.H7)) + ' | Mért vagy számított érték')
			self.H8 = hideg[7]
			Domoticz.Debug(("self.H8 = "+format(self.H8)) + ' | Mért vagy számított érték')
			self.H9 = hideg[8]
			Domoticz.Debug(("self.H9 = "+format(self.H9)) + ' | Mért vagy számított érték')
			self.H10 = hideg[9]
			Domoticz.Debug(("self.H10 = "+format(self.H10)) + ' | Mért vagy számított érték')
			self.H11 = hideg[10]
			Domoticz.Debug(("self.H11 = "+format(self.H11)) + ' | Mért vagy számított érték')
			self.H12 = hideg[11]
			Domoticz.Debug(("self.H12 = "+format(self.H12)) + ' | Mért vagy számított érték')
		else :
			Domoticz.Debug("Missing cold parameter | Hiányzó hideg paraméter")

		normal = parseCSV(Parameters["Mode4"])

		Domoticz.Debug("Normal parameter count | Normál paraméterek száma = "+format(len(normal)))
		if len(normal) >= 12 :
			self.N1 = normal[0]
			Domoticz.Debug(("self.N1 = "+format(self.N1)) + ' | Mért vagy számított érték')
			self.N2 = normal[1]
			Domoticz.Debug(("self.N2 = "+format(self.N2)) + ' | Mért vagy számított érték')
			self.N3 = normal[2]
			Domoticz.Debug(("self.N3 = "+format(self.N3)) + ' | Mért vagy számított érték')
			self.N4 = normal[3]
			Domoticz.Debug(("self.N4 = "+format(self.N4)) + ' | Mért vagy számított érték')
			self.N5 = normal[4]
			Domoticz.Debug(("self.N5 = "+format(self.N5)) + ' | Mért vagy számított érték')
			self.N6 = normal[5]
			Domoticz.Debug(("self.N6 = "+format(self.N6)) + ' | Mért vagy számított érték')
			self.N7 = normal[6]
			Domoticz.Debug(("self.N7 = "+format(self.N7)) + ' | Mért vagy számított érték')
			self.N8 = normal[7]
			Domoticz.Debug(("self.N8 = "+format(self.N8)) + ' | Mért vagy számított érték')
			self.N9 = normal[8]
			Domoticz.Debug(("self.N9 = "+format(self.N9)) + ' | Mért vagy számított érték')
			self.N10 = normal[9]
			Domoticz.Debug(("self.N10 = "+format(self.N10)) + ' | Mért vagy számított érték')
			self.N11 = normal[10]
			Domoticz.Debug(("self.N11 = "+format(self.N11)) + ' | Mért vagy számított érték')
			self.N12 = normal[11]
			Domoticz.Debug(("self.N12 = "+format(self.N12)) + ' | Mért vagy számított érték')
		else :
			Domoticz.Debug("Missing normal parameter | Hiányzó normál paraméter")


		meleg = parseCSV(Parameters["Mode5"])
		Domoticz.Debug("Warm parameter count | Meleg paraméterek száma = "+format(len(meleg)))
		if len(meleg) >= 12:
			self.M1 = meleg[0]
			Domoticz.Debug(("self.M1 = "+format(self.M1)) + ' | Mért vagy számított érték')
			self.M2 = meleg[1]
			Domoticz.Debug(("self.M2 = "+format(self.M2)) + ' | Mért vagy számított érték')
			self.M3 = meleg[2]
			Domoticz.Debug(("self.M3 = "+format(self.M3)) + ' | Mért vagy számított érték')
			self.M4 = meleg[3]
			Domoticz.Debug(("self.M4 = "+format(self.M4)) + ' | Mért vagy számított érték')
			self.M5 = meleg[4]
			Domoticz.Debug(("self.M5 = "+format(self.M5)) + ' | Mért vagy számított érték')
			self.M6 = meleg[5]
			Domoticz.Debug(("self.M6 = "+format(self.M6)) + ' | Mért vagy számított érték')
			self.M7 = meleg[6]
			Domoticz.Debug(("self.M7 = "+format(self.M7)) + ' | Mért vagy számított érték')
			self.M8 = meleg[7]
			Domoticz.Debug(("self.M8 = "+format(self.M8)) + ' | Mért vagy számított érték')
			self.M9 = meleg[8]
			Domoticz.Debug(("self.M9 = "+format(self.M9)) + ' | Mért vagy számított érték')
			self.M10 = meleg[9]
			Domoticz.Debug(("self.M10 = "+format(self.M10)) + ' | Mért vagy számított érték')
			self.M11 = meleg[10]
			Domoticz.Debug(("self.M11 = "+format(self.M11)) + ' | Mért vagy számított érték')
			self.M12 = meleg[11]
			Domoticz.Debug(("self.M12 = "+format(self.M12)) + ' | Mért vagy számított érték')
		else :
			Domoticz.Debug("Missing warm parameter | Hiányzó meleg paraméter")

		# Check support for Domoticz.Status() | ellenőrizze, hogy a gazdagép domoticz verziója támogatja-e a Domoticz.Status() python keretfüggvényt
		try:
			Domoticz.Status(("This version of domoticz allows status logging by the plugin (in verbose mode)") + ' | Állapotinformáció')
		except Exception:
			self.statussupported = False

		# Create missing child devices | hozza létre a gyermekeszközöket, ha ezek még nem léteznek
		devicecreated = []
		if 1 not in Devices:
			Options = {"LevelActions": "||",
				"LevelNames":  self.tl.t("Off|Automata|0|5|10|25|50|75|100%"),
				"LevelOffHidden": "false",
				"SelectorStyle": "1"}
			Domoticz.Device(Name=self.tl.t("Shutter mode"), Unit=1, TypeName="Selector Switch", Switchtype=18, Image=19,
				Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(1, 0, "10")) 
			self.addfavorite(Devices[1].ID)
		if 2 not in Devices:
			Domoticz.Device(Name= self.tl.t("Blind position"), Unit=2, TypeName="Percentage", Used=0).Create()
			devicecreated.append(deviceparam(2, 0, "0"))
		if 3 not in Devices:
			Domoticz.Device(Name= self.tl.t("Target temperature min."), Unit=3, Type=242, Subtype=1, Used=1).Create()
			devicecreated.append(deviceparam(3, 0, "20.0"))
		if 4 not in Devices:
			Domoticz.Device(Name= self.tl.t("Target temperature max."), Unit=4, Type=242, Subtype=1, Used=1).Create()
			devicecreated.append(deviceparam(4, 0, "25.0"))
		if 5 not in Devices:
			Domoticz.Device(Name= self.tl.t("Outside temperature"), Unit=5, Type=242, Subtype=1, Used=0).Create()
			devicecreated.append(deviceparam(5 ,0, "20.0"))
		if 6 not in Devices:
			Domoticz.Device(Name= self.tl.t("Internal temperature"), Unit=6, Type=242, Subtype=1, Used=0).Create()
			devicecreated.append(deviceparam(6 ,0, "20.0"))  # default is 20 fok
		if 7 not in Devices:
			Domoticz.Device(Name= self.tl.t("Lux value"), Unit=7, Type=246, Subtype=1, Used=0).Create()
			devicecreated.append(deviceparam(7 ,0, "0"))  # default is 0 lux
		if 8 not in Devices:
			Domoticz.Device(Name= self.tl.t("Hysteresis"), Unit=8, Type=242, Subtype=1, Used=1).Create()
			devicecreated.append(deviceparam(8, 0, "1"))  # default is 1 fok
		if 9 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|1|2|3|4|5|6|7|8|9|10|20|30|40|50"),
					   "LevelOffHidden": "true",
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Opening lux"), Unit=9, TypeName="Selector Switch", Switchtype=18, Image=19,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(9, 0, "10"))
		if 10 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|10|20|30|50|60|70|80|90"),
					   "LevelOffHidden": "true",
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Strong Light lux"), Unit=10, TypeName="Selector Switch", Switchtype=18, Image=19,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(10, 0, "60"))
		if 11 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|1|2|3|4|5|6|7|8|9|10"),
					   "LevelOffHidden": "true",
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Lux max-min history day"), Unit=11, TypeName="Selector Switch", Switchtype=18, Image=19,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(11, 0, "40"))
		if 12 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|10|20|30|40|50|60|70|80|90|100"),
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Wind speed closing limit km/h"), Unit=12, TypeName="Selector Switch", Switchtype=18, Image=20,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(12, 0, "0"))
		if 15 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|1|2|3|4|5|10|15|20|25|30%"),
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Lux hysteresis percentage"), Unit=15, TypeName="Selector Switch", Switchtype=18, Image=19,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(15, 0, "10"))
		if 16 not in Devices:
			Domoticz.Device(Name= self.tl.t("nyitlux"), Unit=16, Type=246, Subtype=1, Used=0).Create()
			devicecreated.append(deviceparam(16 ,0, "0"))
		if 17 not in Devices:
			Domoticz.Device(Name= self.tl.t("eroslux"), Unit=17, Type=246, Subtype=1, Used=0).Create()
			devicecreated.append(deviceparam(17 ,0, "0"))

		if 18 not in Devices:
			Domoticz.Device(Name= self.tl.t("Wind speed meter"), Unit=18, TypeName="Wind", Subtype=1, Used=0).Create()
			devicecreated.append(deviceparam(18, 0, "0"))
		
		if 19 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|Tilt|Vibrate|Free Fall"),
					   "LevelOffHidden": "false",
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Vibration sensitivity"), Unit=19, TypeName="Selector Switch", Switchtype=18, Image=19,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(19, 0, "20"))

		if 20 not in Devices:
			Domoticz.Device(Name="Vibration status", Unit=20, Type=244, Subtype=73, Switchtype=0, Used=0).Create()
			devicecreated.append(deviceparam(20, 0, "0"))

		if 21 not in Devices:
			Options = {"LevelActions": "||",
					   "LevelNames": self.tl.t("Off|10 minute|30 minute|1 hour|3 hour|6 hour|12 hour"),
					   "LevelOffHidden": "true",
					   "SelectorStyle": "1"}
			Domoticz.Device(Name= self.tl.t("Vibration closing time"), Unit=21, TypeName="Selector Switch", Switchtype=18, Image=19,
							Options=Options, Used=1).Create()
			devicecreated.append(deviceparam(21, 0, "10"))

		if 22 not in Devices:
			Domoticz.Device(Name=self.tl.t("Vibration status alert"), Unit=22, Type=243, Subtype=22, Used=1).Create()
			devicecreated.append(deviceparam(22, 0, self.tl.t("No alert")))
			self.addfavorite(Devices[22].ID)

		if 23 not in Devices:
			Domoticz.Device(Name=self.tl.t("Wind alert"), Unit=23, Type=243, Subtype=22, Used=1).Create()
			devicecreated.append(deviceparam(23, 0, self.tl.t("No alert")))
			self.addfavorite(Devices[23].ID)

		# Initialize newly created devices | ha bármilyen eszközt hoztak létre az onStart()-ban, frissíteni kell az alapértelmezett beállításait
		for device in devicecreated:
			Devices[device.unit].Update(nValue=device.nvalue, sValue=device.svalue)

		# Build sensor and switch lists | listát készít az érzékelőkről és kapcsolókról
		self.OutTempSensors = parse_K(Parameters["Mode1"])
		Domoticz.Debug("Outside sensors | Külső érzékelők = {}".format(self.OutTempSensors))
		
		self.InTempSensors = parse_B(Parameters["Mode1"])
		Domoticz.Debug("Inside sensors | Belső érzékelők = {}".format(self.InTempSensors))
		
		self.FenySensor = parse_F(Parameters["Mode1"])
		Domoticz.Debug("Light sensors | Fényérzékelők = {}".format(self.FenySensor))

		self.WindSensor = parse_S(Parameters["Mode1"])
		Domoticz.Debug(("self.WindSensor = {}".format(self.WindSensor)) + ' | Mért vagy számított érték')

		self.VibrationSensor = parse_V(Parameters["Mode1"])
		Domoticz.Debug(("self.VibrationSensor = {}".format(self.VibrationSensor)) + ' | Mért vagy számított érték')

		self.Redony = parseCSV(Parameters["Mode2"])
		Domoticz.Debug("Shutters | Redőnyök = {}".format(self.Redony))

		# Initialize temperature sensor state | hőmérséklet-érzékelő állapotának felépítése
		for sensor in itertools.chain(self.OutTempSensors, self.InTempSensors):
			self.ActiveSensors[sensor] = True

		self.parameter_change()
		self.applyfavorites()
	
	def parameter_change(self):

		self.targettempmin = float(Devices[3].sValue)
		self.targettemmax = float(Devices[4].sValue)
		self.hiszterezis = float(Devices[8].sValue)

		if Devices[9].sValue == "10" :
			self.nyitlux_param = 1
		elif Devices[9].sValue == "20" :
			self.nyitlux_param = 2
		elif Devices[9].sValue == "30" :
			self.nyitlux_param = 3
		elif Devices[9].sValue == "40" :
			self.nyitlux_param = 4
		elif Devices[9].sValue == "50" :
			self.nyitlux_param = 5
		elif Devices[9].sValue == "60" :
			self.nyitlux_param = 6
		elif Devices[9].sValue == "70" :
			self.nyitlux_param = 7
		elif Devices[9].sValue == "80" :
			self.nyitlux_param = 8
		elif Devices[9].sValue == "90" :
			self.nyitlux_param = 9
		elif Devices[9].sValue == "100" :
			self.nyitlux_param = 10
		elif Devices[9].sValue == "110" :
			self.nyitlux_param = 20
		elif Devices[9].sValue == "120" :
			self.nyitlux_param = 30
		elif Devices[9].sValue == "130" :
			self.nyitlux_param = 40
		elif Devices[9].sValue == "140" :
			self.nyitlux_param = 50


		if Devices[10].sValue == "10" :
			self.eroslux_param = 10
		elif Devices[10].sValue == "20" :
			self.eroslux_param = 20
		elif Devices[10].sValue == "30" :
			self.eroslux_param = 30
		elif Devices[10].sValue == "40" :
			self.eroslux_param = 40
		elif Devices[10].sValue == "50" :
			self.eroslux_param = 50
		elif Devices[10].sValue == "60" :
			self.eroslux_param = 60
		elif Devices[10].sValue == "70" :
			self.eroslux_param = 70
		elif Devices[10].sValue == "80" :
			self.eroslux_param = 80
		elif Devices[10].sValue == "90" :
			self.eroslux_param = 90

		if Devices[11].sValue == "10" :
			self.lastday = 1
		elif Devices[11].sValue == "20" :
			self.lastday = 2
		elif Devices[11].sValue == "30" :
			self.lastday = 3
		elif Devices[11].sValue == "40" :
			self.lastday = 4
		elif Devices[11].sValue == "50" :
			self.lastday = 5
		elif Devices[11].sValue == "60" :
			self.lastday = 6
		elif Devices[11].sValue == "70" :
			self.lastday = 7
		elif Devices[11].sValue == "80" :
			self.lastday = 8
		elif Devices[11].sValue == "90" :
			self.lastday = 9
		elif Devices[11].sValue == "100" :
			self.lastday = 10

		if Devices[12].sValue == "0" :
			self.wind_limit = 0
		elif Devices[12].sValue == "10" :
			self.wind_limit = 10
		elif Devices[12].sValue == "20" :
			self.wind_limit = 20
		elif Devices[12].sValue == "30" :
			self.wind_limit = 30
		elif Devices[12].sValue == "40" :
			self.wind_limit = 40
		elif Devices[12].sValue == "50" :
			self.wind_limit = 50
		elif Devices[12].sValue == "60" :
			self.wind_limit = 60
		elif Devices[12].sValue == "70" :
			self.wind_limit = 70
		elif Devices[12].sValue == "80" :
			self.wind_limit = 80
		elif Devices[12].sValue == "90" :
			self.wind_limit = 90
		elif Devices[12].sValue == "100" :
			self.wind_limit = 100

		if Devices[15].sValue in ("0", "Off") :
			self.lux_hiszterezis = 0
		elif Devices[15].sValue == "10" :
			self.lux_hiszterezis = 1
		elif Devices[15].sValue == "20" :
			self.lux_hiszterezis = 2
		elif Devices[15].sValue == "30" :
			self.lux_hiszterezis = 3
		elif Devices[15].sValue == "40" :
			self.lux_hiszterezis = 4
		elif Devices[15].sValue == "50" :
			self.lux_hiszterezis = 5
		elif Devices[15].sValue == "60" :
			self.lux_hiszterezis = 10
		elif Devices[15].sValue == "70" :
			self.lux_hiszterezis = 15
		elif Devices[15].sValue == "80" :
			self.lux_hiszterezis = 20
		elif Devices[15].sValue == "90" :
			self.lux_hiszterezis = 25
		elif Devices[15].sValue == "100" :
			self.lux_hiszterezis = 30

		if Devices[19].sValue == "0":
			self.vibration_limit = None
		elif Devices[19].sValue == "10":
			self.vibration_limit = "Set Level: 10 %"
		elif Devices[19].sValue == "20":
			self.vibration_limit = "Set Level: 20 %"
		elif Devices[19].sValue == "30":
			self.vibration_limit = "Set Level: 30 %"


		if Devices[21].sValue == "10" :
			self.vibration_time_limit = 10
		elif Devices[21].sValue == "20" :
			self.vibration_time_limit = 30
		elif Devices[21].sValue == "30" :
			self.vibration_time_limit = 60
		elif Devices[21].sValue == "40" :
			self.vibration_time_limit = 180
		elif Devices[21].sValue == "50" :
			self.vibration_time_limit = 360
		elif Devices[21].sValue == "60" :
			self.vibration_time_limit = 720
		


	def onStop(self):
		Domoticz.Debugging(0)


	def onCommand(self, Unit, Command, Level, Color):

		Domoticz.Debug(("onCommand called for Unit {}: Command '{}', Level: {}".format(Unit, Command, Level)) + ' | Mért vagy számított érték')

		nvalue = 1 if Level > 0 else 0
		svalue = str(Level)

		Devices[Unit].Update(nValue=nvalue, sValue=svalue)

		if Unit in (1, 3, 4 ): 
			self.nextupdate = datetime.now()
			self.last_vibration = None
			self.onHeartbeat()
		
		if Unit in (8, 9, 10, 11, 12, 13, 14, 15, 19, 21 ) :
			Domoticz.Debug("Device setting changed | Eszközbeállítás megváltozott")
			self.nextupdate = datetime.now()
			self.parameter_change()


	def onHeartbeat(self):

		vibration_alert_msg = self.tl.t("No alert")
		wind_alert_msg = self.tl.t("No alert")

		if self.VibrationSensor and self.Redony and Devices[1].sValue != "0" :

			Domoticz.Debug((f"self.last_vibration = {self.last_vibration}") + ' | Mért vagy számított érték')

			if isinstance(self.last_vibration, datetime):
				expire_time = self.last_vibration + timedelta(minutes=self.vibration_time_limit)
				Domoticz.Debug((f"self.vibration_time_limit = {self.vibration_time_limit}") + ' | Mért vagy számított érték')
				Domoticz.Debug((f"expire_time = {expire_time}") + ' | Mért vagy számított érték')
				if datetime.now() < expire_time:
					Domoticz.Debug("Keep shutters closed during vibration hold | Redőnyök zárva tartása rezgés miatt")
					vibration_alert_msg = self.tl.t("Vibration alert")
				else:
					Domoticz.Debug("Vibration hold expired | Rezgés miatti zárás lejárt")
					self.last_vibration = None
					self.nextupdate = datetime.now()
			else:
				self.readVibration()
				if self.aktvibration:
					if self.LastSwitchTime(self.Redony[0]):
						self.last_vibration = datetime.now()
						self.redonypercent(0)
						vibration_alert_msg = self.tl.t("Vibration alert")

			vibration_nvalue = 4 if vibration_alert_msg.strip() != self.tl.t("No alert").strip() else 0
			if Devices[22].sValue.strip() != vibration_alert_msg.strip() or Devices[22].nValue != vibration_nvalue:
				Domoticz.Debug(f"Updating | Frissítés: Vibration alert changed | Rezgésriasztás megváltozott -> nValue={vibration_nvalue}, sValue='{vibration_alert_msg}'")
				Devices[22].Update(nValue=vibration_nvalue, sValue=vibration_alert_msg)
			else:
				Domoticz.Debug("Vibration alert unchanged, no update | Rezgésriasztás nem változott, nincs frissítés")


		if Devices[1].sValue != "0":
			self.switchJelenlet()

		if (self.nextupdate <= datetime.now() or self.lastjelenletInfo != self.jelenletInfo) and not self.last_vibration :

			self.nextupdate = datetime.now() + timedelta(minutes=self.nextupdatetime)
			
			self.met_date_load()

			self.find_now_metdata()
			
			self.readLux()
			
			self.readTemps()

			self.readWind()

			self.lastjelenletInfo = self.jelenletInfo
			
			self.lastintemp = self.intemp

			if Devices[1].sValue == "0":  # Rendszer kikapcsolva
				Domoticz.Debug("Controller disabled | Vezérlő kikapcsolva")
				
			elif self.last_wind_limit :
				self.last_wind_limit = False
				self.redonypercent(0)

			elif self.wind_limit != 0 and self.wind > self.wind_limit:
				Domoticz.Debug("High wind: closing shutters | Erős szél: redőnyök zárása")
				self.last_wind_limit = True
				self.redonypercent(0)
				wind_alert_msg = self.tl.t("Wind alert")

			elif Devices[1].sValue == "20":  # le
				Domoticz.Debug(("redony 0%") + ' | Mért vagy számított érték')
				self.redonypercent(0)

			elif Devices[1].sValue == "30":  # le
				Domoticz.Debug(("redony 5%") + ' | Mért vagy számított érték')
				self.redonypercent(5)

			elif Devices[1].sValue == "40":  # le
				Domoticz.Debug(("redony 10%") + ' | Mért vagy számított érték')
				self.redonypercent(10)

			elif Devices[1].sValue == "50":  # 25%
				Domoticz.Debug(("redony 25%") + ' | Mért vagy számított érték')
				self.redonypercent(25)

			elif Devices[1].sValue == "60":  # 50%
				Domoticz.Debug(("redony 50%") + ' | Mért vagy számított érték')
				self.redonypercent(50)

			elif Devices[1].sValue == "70":  # 75%
				Domoticz.Debug(("redony 75%") + ' | Mért vagy számított érték')
				self.redonypercent(75)

			elif Devices[1].sValue == "80":  # 100%
				Domoticz.Debug(("redony 100%") + ' | Mért vagy számított érték')
				self.redonypercent(100)

			elif Devices[1].sValue == "10":  # automata 
				
				Domoticz.Debug("Automatic shutter mode | Automatikus redőnyvezérlés")

				if self.intemp <= self.targettempmin :
					Domoticz.Debug("Indoor temperature below minimum target | Belső hőmérséklet a minimum célérték alatt")
				
					if self.intemp > self.outtemp :
						Domoticz.Debug("Colder outside than inside | Kint hidegebb van, mint bent")
						if self.lux <= self.nyitlux :
							Domoticz.Debug("Lux below opening threshold | Luxérték a nyitási küszöb alatt")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.H4 = "+format(self.H4)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H4)
							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.H1 = "+format(self.H1)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H1)

						elif self.nyitlux < self.lux < self.eroslux :
							Domoticz.Debug("Lux between opening and strong-light thresholds | Luxérték a nyitási és erős fény küszöb között")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.H5 = "+format(self.H5)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H5)
							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.H2 = "+format(self.H2)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H2)

						elif self.lux >= self.eroslux :
							Domoticz.Debug("Lux above strong-light threshold | Luxérték az erős fény küszöb felett")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.H6 = "+format(self.H6)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H6)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.H3 = "+format(self.H3)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H3)

					else :
						Domoticz.Debug("Warmer outside than inside | Kint melegebb van, mint bent")
						if self.lux <= self.nyitlux :
							Domoticz.Debug("Lux below opening threshold | Luxérték a nyitási küszöb alatt")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.H10 = "+format(self.H10)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H10)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.H7 = "+format(self.H7)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H7)

						elif self.nyitlux < self.lux < self.eroslux :
							Domoticz.Debug("Lux between opening and strong-light thresholds | Luxérték a nyitási és erős fény küszöb között")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.H11 = "+format(self.H11)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H11)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.H8 = "+format(self.H8)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H8)

						elif self.lux >= self.eroslux :
							Domoticz.Debug("Lux above strong-light threshold | Luxérték az erős fény küszöb felett")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.H12 = "+format(self.H12)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H12)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.H9 = "+format(self.H9)) + ' | Mért vagy számított érték')
								self.redonypercent(self.H9)


				elif self.intemp > self.targettemmax and self.intemp >= self.targettemmax :
					Domoticz.Debug(("Melegebb van bent mint a célmax") + ' | Mért vagy számított érték')

					if self.intemp > self.outtemp :
						Domoticz.Debug("Colder outside than inside | Kint hidegebb van, mint bent")
						if self.lux <= self.nyitlux :
							Domoticz.Debug("Lux below opening threshold | Luxérték a nyitási küszöb alatt")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.M4 = "+format(self.M4)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M4)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.M1 = "+format(self.M1)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M1)

						
						elif self.nyitlux < self.lux < self.eroslux :
							Domoticz.Debug("Lux between opening and strong-light thresholds | Luxérték a nyitási és erős fény küszöb között")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.M5 = "+format(self.M5)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M5)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.M2 = "+format(self.M2)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M2)

						elif self.lux >= self.eroslux :
							Domoticz.Debug("Lux above strong-light threshold | Luxérték az erős fény küszöb felett")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.M6 = "+format(self.M6)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M6)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.M3 = "+format(self.M3)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M3)


					else :
						Domoticz.Debug("Warmer outside than inside | Kint melegebb van, mint bent")
						if self.lux <= self.nyitlux :
							Domoticz.Debug("Lux below opening threshold | Luxérték a nyitási küszöb alatt")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.M10 = "+format(self.M10)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M10)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.M7 = "+format(self.M7)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M7)

						elif self.nyitlux < self.lux < self.eroslux :
							Domoticz.Debug("Lux between opening and strong-light thresholds | Luxérték a nyitási és erős fény küszöb között")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.M11 = "+format(self.M11)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M11)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.M8 = "+format(self.M8)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M8)

						elif self.lux >= self.eroslux :
							Domoticz.Debug("Lux above strong-light threshold | Luxérték az erős fény küszöb felett")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.M12 = "+format(self.M12)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M12)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.M9 = "+format(self.M9)) + ' | Mért vagy számított érték')
								self.redonypercent(self.M9)

				else :
					Domoticz.Debug("Indoor temperature between target limits | Belső hőmérséklet a célértékek között")

					if self.intemp > self.outtemp :
						Domoticz.Debug("Colder outside than inside | Kint hidegebb van, mint bent")
						if self.lux <= self.nyitlux :
							Domoticz.Debug("Lux below opening threshold | Luxérték a nyitási küszöb alatt")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.N4 = "+format(self.N4)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N4)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.N1 = "+format(self.N1)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N1)

						elif self.nyitlux < self.lux < self.eroslux :
							Domoticz.Debug("Lux between opening and strong-light thresholds | Luxérték a nyitási és erős fény küszöb között")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.N5 = "+format(self.N5)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N5)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.N2 = "+format(self.N2)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N2)

						elif self.lux >= self.eroslux :
							Domoticz.Debug("Lux above strong-light threshold | Luxérték az erős fény küszöb felett")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.N6 = "+format(self.N6)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N6)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.N3 = "+format(self.N3)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N3)

					else :
						Domoticz.Debug("Warmer outside than inside | Kint melegebb van, mint bent")
						if self.lux <= self.nyitlux :
							Domoticz.Debug("Lux below opening threshold | Luxérték a nyitási küszöb alatt")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.N10 = "+format(self.N10)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N10)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.N7 = "+format(self.N7)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N7)

						elif self.nyitlux < self.lux < self.eroslux :
							Domoticz.Debug("Lux between opening and strong-light thresholds | Luxérték a nyitási és erős fény küszöb között")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.N11 = "+format(self.N11)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N11)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.N8 = "+format(self.N8)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N8)

						elif self.lux >= self.eroslux :
							Domoticz.Debug("Lux above strong-light threshold | Luxérték az erős fény küszöb felett")
							if self.jelenletInfo == True :
								Domoticz.Debug("Presence detected | Jelenlét érzékelve")
								Domoticz.Debug(("self.N12 = "+format(self.N12)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N12)

							else :
								Domoticz.Debug("No presence detected | Nem érzékelhető jelenlét")
								Domoticz.Debug(("self.N9 = "+format(self.N9)) + ' | Mért vagy számított érték')
								self.redonypercent(self.N9)
		

			wind_nvalue = 4 if wind_alert_msg.strip() != self.tl.t("No alert").strip() else 0
			if Devices[23].sValue.strip() != wind_alert_msg.strip() or Devices[23].nValue != wind_nvalue:
				Domoticz.Debug(f"Updating | Frissítés: Wind alert changed | Szélriasztás megváltozott -> nValue={wind_nvalue}, sValue='{wind_alert_msg}'")
				Devices[23].Update(nValue=wind_nvalue, sValue=wind_alert_msg)
			else:
				Domoticz.Debug("Wind alert unchanged, no update | Szélriasztás nem változott, nincs frissítés")

		else :
			Domoticz.Debug(("Nincs frissités, nincs még itt az ideje, majd:"+format(self.nextupdate)) + ' | Mért vagy számított érték')


	def OpenMeteoAPI(self):
		# Fetch hourly forecast directly from Open-Meteo | Óránkénti előrejelzés közvetlen lekérése az Open-Meteótól
		try:
			latitude, longitude = map(float, self.location[:2])
			query = parse.urlencode({
				"latitude": latitude, "longitude": longitude,
				"hourly": "temperature_2m,precipitation,wind_speed_10m,shortwave_radiation",
				"timezone": "auto", "forecast_days": 3,
			})
			url = "https://api.open-meteo.com/v1/forecast?" + query
			Domoticz.Debug(f"Requesting Open-Meteo forecast | Open-Meteo előrejelzés lekérése: {url}")
			with request.urlopen(request.Request(url, headers={"User-Agent": "Domoticz-ASC/1.3.1"}), timeout=10) as response:
				data = json.load(response)
			hourly = data["hourly"]
			keys = ("time", "temperature_2m", "precipitation", "wind_speed_10m", "shortwave_radiation")
			if not all(isinstance(hourly.get(k), list) for k in keys):
				raise ValueError("Missing hourly weather arrays")
			count = len(hourly["time"])
			if not all(len(hourly[k]) == count for k in keys):
				raise ValueError("Inconsistent hourly forecast array lengths")
			forecast = []
			for i in range(count):
				if any(hourly[k][i] is None for k in keys):
					continue
				# Radiation (W/m²) to approximate illuminance (lux), not a measured lux value | Sugárzás (W/m²) becsült megvilágítássá (lux), nem mért luxérték
				forecast.append({
					"time": datetime.fromisoformat(hourly["time"][i]).strftime("%Y-%m-%d %H:%M:%S"),
					"temp": float(hourly["temperature_2m"][i]),
					"rain": float(hourly["precipitation"][i]),
					"wind": float(hourly["wind_speed_10m"][i]),
					"lux": max(0.0, float(hourly["shortwave_radiation"][i]) * 120.0),
				})
			if not forecast:
				raise ValueError("Empty hourly forecast")
			return forecast
		except Exception as e:
			Domoticz.Error(f"Open-Meteo forecast request failed | Open-Meteo előrejelzés lekérése sikertelen: {e}")
			return None


	def switchJelenlet(self):
		
		if self.jelenlet is not None:
			Domoticz.Debug(("self.jelenlet name: "+format(self.jelenlet)) + ' | Mért vagy számított érték')
			self.jelenletInfo = JelenletAPI(self.jelenlet)
			Domoticz.Debug(("jelenletInfo: "+format(self.jelenletInfo)) + ' | Mért vagy számított érték')
		else: 
			self.jelenletInfo = True


	def redonypercent(self,percent):

		command = "Set Level&level="+str(percent)

		Domoticz.Debug(("percent: "+format(percent)) + ' | Mért vagy számított érték')

		Domoticz.Debug(("command: "+format(command)) + ' | Mért vagy számított érték')
		devicesAPI = DomoticzAPI(
			"type=devices&filter=light&order=Name" 
			if float(Parameters["DomoticzVersion"]) <= 2023.1 
			else "type=command&param=getdevices&filter=light&order=Name"
		)
		if isinstance(devicesAPI, dict) and isinstance(devicesAPI.get("result"), list):
			for device in devicesAPI["result"]:
				idx = int(device["idx"])
				if idx in self.Redony:
					Domoticz.Debug(("type=command&param=switchlight&idx={}&switchcmd={}".format(idx, command)) + ' | Mért vagy számított érték')
					DomoticzAPI("type=command&param=switchlight&idx={}&switchcmd={}".format(idx, command))
					Devices[2].Update(nValue=0, sValue=str(percent), TimedOut=False)
		else:
			Domoticz.Error("Device API error | Eszköz API-hiba")


	def readTemps(self):

		# Read devices from the API | lekérni az összes eszközt az API-ból
		noerror = True
		listintemps = []
		listouttemps = []
		devicesAPI = DomoticzAPI(
			"type=devices&filter=temp&order=Name" 
			if float(Parameters["DomoticzVersion"]) <= 2023.1 
			else "type=command&param=getdevices&filter=temp&order=Name"
		)
		if isinstance(devicesAPI, dict) and isinstance(devicesAPI.get("result"), list):
			for device in devicesAPI["result"]:  # elemzi a hőmérséklet-érzékelőket
				idx = int(device["idx"])
				if idx in self.InTempSensors:
					if "Temp" in device:
						Domoticz.Debug(("device: {}-{} = {}".format(device["idx"], device["Name"], device["Temp"])) + ' | Mért vagy számított érték')
						if not self.SensorTimedOut(idx, device["Name"], device["LastUpdate"]):
							listintemps.append(device["Temp"])
					else:
						Domoticz.Error(("device: {}-{} is not a Temperature sensor".format(device["idx"], device["Name"])) + ' | Hiba részletei')
				
				if idx in self.OutTempSensors:
					if "Temp" in device:
						Domoticz.Debug(("device: {}-{} = {}".format(device["idx"], device["Name"], device["Temp"])) + ' | Mért vagy számított érték')
						if not self.SensorTimedOut(idx, device["Name"], device["LastUpdate"]):
							listouttemps.append(device["Temp"])
					else:
						Domoticz.Error(("device: {}-{} is not a Temperature sensor".format(device["idx"], device["Name"])) + ' | Hiba részletei')


		# Calculate average indoor temperature | számítsa ki az átlagos belső hőmérsékletet
		nbtemps = len(listintemps)
		if nbtemps > 0:
			self.aktintemp = round(sum(listintemps) / nbtemps, 1)

			if self.aktintemp > self.lastintemp + self.hiszterezis or self.aktintemp < self.lastintemp - self.hiszterezis:
				 self.intemp = self.aktintemp
			else :
				self.intemp = self.lastintemp

			self.lastintemp = self.intemp

		else:
			Domoticz.Debug("No indoor temperature sensor found | Nem található belső hőmérséklet-érzékelő")
			self.intemp = 22.0

		Devices[6].Update(nValue=0, sValue=str(self.intemp), TimedOut=False)

		# Calculate average outdoor temperature | számítsa ki az átlagos külső hőmérsékletet
		nbtemps = len(listouttemps)
		if nbtemps > 0:
			self.aktouttemp = round(sum(listouttemps) / nbtemps, 1)

			if self.aktouttemp > self.lastouttemp + self.hiszterezis or self.aktouttemp < self.lastouttemp - self.hiszterezis :
				 self.outtemp = self.aktouttemp
			else :
				self.outtemp = self.lastouttemp

			self.lastouttemp = self.outtemp
		
		elif self.now_outtemp is not None:
			self.outtemp = self.now_outtemp
			
		else :
			Domoticz.Debug("No outdoor temperature sensor found | Nem található külső hőmérséklet-érzékelő")
			self.outtemp = 20.0

		Devices[5].Update(nValue=0, sValue=str(self.outtemp), TimedOut=False)

		return noerror

	def get_sun_times(self):
		result = DomoticzAPI("type=command&param=getSunRiseSet")
		if result and "Sunrise" in result and "Sunset" in result:
			return result["Sunrise"], result["Sunset"]
		return None, None


	def readLux(self):
		
		Domoticz.Debug("Starting lux processing | Luxadatok feldolgozása indul")
		
		self.luxhistory = DomoticzAPI("type=command&param=graph&sensor=counter&range=month&idx={}".format(Devices[7].ID))

		Domoticz.Debug(("self.luxhistory = " + format(self.luxhistory)) + ' | Mért vagy számított érték')

		if not isinstance(self.luxhistory, dict) or not isinstance(self.luxhistory.get("result"), list):
			Domoticz.Error("Lux history is unavailable; using safe defaults | A luxelőzmények nem érhetők el; biztonságos alapértékek használata")
			self.luxhistory = {"result": []}

		Domoticz.Debug(("self.lastday = " + str(self.lastday)) + ' | Mért vagy számított érték')

		# Get current and starting timestamps | Get current timestamp and calculate start_date timestamp
		today_timestamp = time.time()
		start_date_timestamp = today_timestamp - (self.lastday * 86400)  # Convert days to seconds

		Domoticz.Debug((f"Start timestamp: {start_date_timestamp}, Today timestamp: {today_timestamp}") + ' | Mért vagy számított érték')

		try:
			filtered_data = []
			for entry in self.luxhistory['result']:
				if 'd' not in entry:
					Domoticz.Error((f"Missing 'd' key in entry: {entry}") + ' | Hiba részletei')
					continue

				# Convert record date to timestamp | Convert entry date to timestamp
				entry_timestamp = to_timestamp(entry['d'])
				if entry_timestamp is None:
					continue

				if start_date_timestamp <= entry_timestamp < today_timestamp:
					filtered_data.append(entry)

			if not filtered_data:
				Domoticz.Error("No valid lux history records | Nincs érvényes luxelőzmény")
			
			# Calculate minimum and maximum lux | Min and max lux values calculation
			minlux_values = []
			maxlux_values = []

			for entry in filtered_data:
				if 'lux_min' in entry:
					try:
						minlux_values.append(float(entry['lux_min']))
					except ValueError as e:
						Domoticz.Error((f"Error converting 'lux_min' to float: {entry['lux_min']}, error: {e}") + ' | Hiba részletei')
				else:
					Domoticz.Debug((f"No 'lux_min' in entry: {entry}") + ' | Mért vagy számított érték')

				if 'lux_max' in entry:
					try:
						maxlux_values.append(float(entry['lux_max']))
					except ValueError as e:
						Domoticz.Error((f"Error converting 'lux_max' to float: {entry['lux_max']}, error: {e}") + ' | Hiba részletei')
				else:
					Domoticz.Debug((f"No 'lux_max' in entry: {entry}") + ' | Mért vagy számított érték')

			# Set minimum and maximum lux | Set min_lux and max_lux values
			Domoticz.Debug(("minlux_values = " + format(minlux_values)) + ' | Mért vagy számított érték')
			Domoticz.Debug(("maxlux_values = " + format(maxlux_values)) + ' | Mért vagy számított érték')
			self.min_lux = round(sum(minlux_values) / len(minlux_values), 2) if minlux_values else 1
			self.max_lux = round(sum(maxlux_values) / len(maxlux_values), 2) if maxlux_values else 10000

			Domoticz.Debug((f"self.min_lux = {self.min_lux}, self.max_lux = {self.max_lux}") + ' | Mért vagy számított érték')

		except Exception as e:
			Domoticz.Error(("Error in processing lux history data: " + str(e)) + ' | Hiba részletei')

		# Calculate opening and strong-light thresholds | Calculate nyitlux and eroslux
		if self.nyitlux_param is None:
			Domoticz.Error(("nyitlux_param is None.") + ' | Hiba részletei')

		self.nyitlux = float(self.min_lux + self.nyitlux_param)
		Domoticz.Debug(("self.nyitlux = " + str(self.nyitlux)) + ' | Mért vagy számított érték')
		Devices[16].Update(nValue=0, sValue=str(self.nyitlux), TimedOut=False)

		self.eroslux = float((self.max_lux * self.eroslux_param) / 100)

		if self.nyitlux >= self.eroslux:
			Domoticz.Error(f"Invalid lux thresholds: opening={self.nyitlux}, strong={self.eroslux} | Hibás luxhatárok: nyitási={self.nyitlux}, erős={self.eroslux}")

		Domoticz.Debug(("self.eroslux = " + str(self.eroslux)) + ' | Mért vagy számított érték')
		Devices[17].Update(nValue=0, sValue=str(self.eroslux), TimedOut=False)

		# Read available light sensors | Fetch all devices for light sensors
		listlux = []
		Domoticz.Debug((f"self.FenySensor = {self.FenySensor}") + ' | Mért vagy számított érték')

		luxdevicesAPI = DomoticzAPI(
			"type=devices&filter=utility&order=Name" 
			if float(Parameters["DomoticzVersion"]) <= 2023.1 
			else "type=command&param=getdevices&filter=utility&order=Name"
		)

		if not luxdevicesAPI or 'result' not in luxdevicesAPI:
			Domoticz.Error("Cannot read lux sensor devices | Nem olvashatók a luxérzékelők")

		if luxdevicesAPI and isinstance(luxdevicesAPI.get("result"), list):
			for device in luxdevicesAPI["result"]:
				idx = int(device["idx"])
				if idx in self.FenySensor:
					Domoticz.Debug((f"idx = {idx}") + ' | Mért vagy számított érték')
					if "Data" in device:
						Domoticz.Debug((f"device: {device['idx']}-{device['Name']} = {device['Data']}") + ' | Mért vagy számított érték')
						if not self.SensorTimedOut(idx, device["Name"], device["LastUpdate"]):
							listlux.append(int(device["Data"].split()[0]))
					else:
						Domoticz.Error((f"device: {device['idx']}-{device['Name']} is not a Lux sensor") + ' | Hiba részletei')

		# Calculate average illuminance | Átlagos megvilágítás számítása
		nblux = len(listlux)
		Domoticz.Debug(f"Forecast lux | Előrejelzett lux: {self.now_lux}")

		if nblux > 0:
			self.aktlux = round(sum(listlux) / nblux, 1)
			self.luxhiszterezis = max(1.0, max(self.aktlux, self.lastlux) * self.lux_hiszterezis / 100)

			if self.aktlux <= self.nyitlux or self.lastlux <= self.nyitlux < self.aktlux:
				self.lux = self.aktlux
			elif abs(self.aktlux - self.lastlux) > self.luxhiszterezis:
				self.lux = self.aktlux
			else:
				self.lux = self.lastlux

			self.lastlux = self.lux
			Domoticz.Debug(f"Measured lux | Mért lux: {self.aktlux}, accepted={self.lux}, hysteresis={self.luxhiszterezis}")
		else:
			# Use forecast lux if available | Ha van now_lux → ezt használd
			if self.now_lux is not None:
				self.lux = self.now_lux
			else:
				# No sensor or forecast: use daylight fallback | Nincs szenzor, nincs now_lux → napkeltétől napnyugtáig eroslux, máskor 0
				sunrise, sunset = self.get_sun_times()
				now = datetime.now().strftime("%H:%M")

				if sunrise and sunset and sunrise <= now <= sunset:
					self.lux = self.eroslux
				else:
					self.lux = 0.0

		self.lastlux = self.lux
		Devices[7].Update(nValue=0, sValue=str(self.lux), TimedOut=False)
		return True

	def readWind(self):

		# Read devices from the API | lekérni az összes eszközt az API-ból
		noerror = True
		listwind = []
		devicesAPI = DomoticzAPI(
			"type=devices&order=Name" 
			if float(Parameters["DomoticzVersion"]) <= 2023.1 
			else "type=command&param=getdevices&order=Name"
		)
		if isinstance(devicesAPI, dict) and isinstance(devicesAPI.get("result"), list):
			for device in devicesAPI["result"]:
				idx = int(device["idx"])
				if idx in self.WindSensor:
					if "Data" in device:
						Domoticz.Debug(("device: {}-{} = {}".format(device["idx"], device["Name"], device["Data"])) + ' | Mért vagy számított érték')
						dwind = device["Data"]
						cdwind = float(dwind.split(";")[2])
						Domoticz.Debug((f"device wind = {cdwind}") + ' | Mért vagy számított érték')
						if not self.SensorTimedOut(idx, device["Name"], device["LastUpdate"]):
							listwind.append(cdwind)
					else:
						Domoticz.Error(("device: {}-{} is not a Wind sensor".format(device["idx"], device["Name"])) + ' | Hiba részletei')


		# Calculate average wind speed | számítsa ki az átlagos szélsebességet
		nbwinds = len(listwind)
		if nbwinds > 0:
			self.wind = round(sum(listwind) / nbwinds, 1)
		else:
			Domoticz.Debug("No wind sensor found | Nem található szélérzékelő")
			self.wind = self.now_wind if self.now_wind is not None else 0.0

		svalue = f"0;N;{self.wind};0;0;0"

		Devices[18].Update(nValue=0, sValue=svalue)

		Domoticz.Debug((f"self.wind svalue = {svalue}") + ' | Mért vagy számított érték')

		return noerror

	def readVibration(self):

		# Read devices from the API | lekérni az összes eszközt az API-ból
		Domoticz.Debug("Reading vibration sensor | Rezgésérzékelő lekérése")
		self.aktvibration = False
		noerror = True
		listvibration = []
		devicesAPI = DomoticzAPI(
			"type=devices&order=Name" 
			if float(Parameters["DomoticzVersion"]) <= 2023.1 
			else "type=command&param=getdevices&order=Name"
		)
		if isinstance(devicesAPI, dict) and isinstance(devicesAPI.get("result"), list):
			for device in devicesAPI["result"]:
				idx = int(device["idx"])
				if idx in self.VibrationSensor:
					if "Data" in device:
						Domoticz.Debug((f"self.vibration_limit = {self.vibration_limit}") + ' | Mért vagy számított érték')
						Domoticz.Debug(("device: {}-{} = {}".format(device["idx"], device["Name"], device["Data"])) + ' | Mért vagy számított érték')
						if device["Data"] == self.vibration_limit :
							self.aktvibration = True
							Domoticz.Debug((f"self.aktvibration = {self.aktvibration}") + ' | Mért vagy számított érték')
					else:
						Domoticz.Error(("device: {}-{} is not a Vibration sensor".format(device["idx"], device["Name"])) + ' | Hiba részletei')


		nvalue = 1 if self.aktvibration else 0
		svalue = "On" if self.aktvibration else "Off"

		Devices[20].Update(nValue=nvalue, sValue=svalue)

		Domoticz.Debug((f"self.aktvibration → nValue = {nvalue}, sValue = {svalue}") + ' | Mért vagy számított érték')

		return noerror

	def SensorTimedOut(self, idx, name, datestring):

		def LastUpdate(datestring):
			dateformat = "%Y-%m-%d %H:%M:%S"
			try:
				result = datetime.strptime(datestring, dateformat)
			except TypeError:
				result = datetime(*(time.strptime(datestring, dateformat)[0:6]))
			return result

		timeout_minutes = int(Settings.get("SensorTimeout", 60))
		timedout = LastUpdate(datestring) + timedelta(minutes=timeout_minutes) < datetime.now()

		# Initialize sensor state if missing | ha az idx még nincs a dict-ben, alapértelmezett érték
		if idx not in self.ActiveSensors:
			self.ActiveSensors[idx] = True

		if timedout:
			if self.ActiveSensors[idx]:
				Domoticz.Error(("skipping timed out temperature sensor '{}'".format(name)) + ' | Hiba részletei')
				self.ActiveSensors[idx] = False
		else:
			if not self.ActiveSensors[idx]:
				self.WriteLog("previously timed out temperature sensor '{}' is back online".format(name), "Status")
				self.ActiveSensors[idx] = True

		return timedout


	def WriteLog(self, message, level="Normal"):

		if (self.loglevel == "Verbose" and level == "Verbose") or level == "Status":
			if self.statussupported:
				Domoticz.Status(message)
			else:
				Domoticz.Log(message)
		elif level == "Normal":
			Domoticz.Log(message)


	def met_date_load(self):

		Domoticz.Debug("Starting weather data load | Időjárásadatok betöltése indul")

		# Ensure forecast cache is a list | --- GLOBÁLIS VÉDELEM: met_data_string mindig legyen lista ---
		if not isinstance(self.met_data_string, list):
			Domoticz.Error("Invalid weather cache, reset to empty list | Érvénytelen időjárás-gyorsítótár, üres listára állítva")
			self.met_data_string = []

		# Initial load if weather cache is empty | Ha üres → első töltés
		if len(self.met_data_string) == 0:
			Domoticz.Debug("Weather cache empty, loading | Üres időjárás-gyorsítótár, betöltés")

			data = self.OpenMeteoAPI()

			# Handle failed or empty API response safely | Ha API tiltás / hiba / üres → NE OMOLJON ÖSSZE
			if not isinstance(data, list) or len(data) == 0:
				Domoticz.Error("Weather API failed; cached data kept | Időjárás-API hiba, korábbi adatok megmaradnak")
				return

			self.met_data_string = data
			Domoticz.Debug("Weather cache loaded | Időjárásadatok betöltve")
			return

		# Weather data cache is nonempty | --- Itt már biztos, hogy van valamennyi adat ---
		try:
			valid_entries = [
				entry for entry in self.met_data_string
				if isinstance(entry, dict) and 'time' in entry
			]

			if len(valid_entries) == 0:
				raise ValueError("met_data_string-ben nincs egyetlen valid 'time' mező")

			max_date = max(
				time.mktime(time.strptime(entry['time'], '%Y-%m-%d %H:%M:%S'))
				for entry in valid_entries
			)

			

			Domoticz.Debug((f"max_date = {max_date}") + ' | Mért vagy számított érték')
			

			# Forecast refresh condition | --- FRISSÍTÉS FELTÉTELE ---
			if max_date < time.time() + 120:
				Domoticz.Debug("Forecast does not cover next hour, refreshing | Az előrejelzés nem fedi a következő órát, frissítés")

				data = self.OpenMeteoAPI()  # SAFE LOAD

				# Keep previous forecast on invalid response | Ha hibás / None → nem írjuk felül a régit!
				if not isinstance(data, list) or len(data) == 0:
					Domoticz.Error("Invalid updated forecast; old data kept | Hibás frissített előrejelzés; régi adatok megmaradnak")
					return

				self.met_data_string = data
				Domoticz.Debug("Weather data refreshed | Időjárásadatok frissítve")
			else:
				Domoticz.Debug("Cached forecast still valid | A tárolt előrejelzés még érvényes")

		except Exception as e:
			Domoticz.Error(f"Weather data load failed | Hiba az időjárásadatok betöltésekor: {e}")

			# Retry data loading safely | Újratöltés (biztonságosan)
			data = self.OpenMeteoAPI()

			if not isinstance(data, list) or len(data) == 0:
				Domoticz.Error("Invalid replacement forecast; cached data kept | A cserélt előrejelzés hibás; a korábbi adatok megmaradnak")
				return

			self.met_data_string = data
			Domoticz.Debug("Weather cache reloaded after error | Időjárásadatok újratöltve hiba után")

		Domoticz.Debug("Weather data load finished | Időjárásadatok betöltése kész")


	def find_now_metdata(self):

		# Guard against missing or empty forecast | --- GLOBÁLIS BIZTONSÁG: ha nincs adat lista, vagy üres ---
		if not isinstance(self.met_data_string, list) or len(self.met_data_string) == 0:
			Domoticz.Error("No valid weather forecast; skipping interpolation | Nincs érvényes előrejelzés; interpoláció kihagyva")
			self.now_outtemp = None
			self.now_lux = None
			self.now_rain = None
			self.now_wind = None
			return

		now = datetime.now()
		minute = now.minute

		hour_start = now.replace(minute=0, second=0, microsecond=0)
		next_hour = hour_start + timedelta(hours=1)

		prev_time_str = hour_start.strftime('%Y-%m-%d %H:%M:%S')
		next_time_str = next_hour.strftime('%Y-%m-%d %H:%M:%S')

		# Find matching hourly records | Megfelelő rekordok keresése
		prev_hour = next((x for x in self.met_data_string
			if isinstance(x, dict) and x.get("time") == prev_time_str), None)

		next_hour_data = next((x for x in self.met_data_string
			if isinstance(x, dict) and x.get("time") == next_time_str), None)

		# Guard against missing current-hour forecast | --- Ha nincs előző órás adat → teljes hiba elleni védelem ---
		if not prev_hour:
			Domoticz.Error(f"No hourly weather record | Hiányzik az órás időjárásrekord ({prev_time_str})")

			self.now_outtemp = None
			self.now_lux = None
			self.now_rain = None
			self.now_wind = None
			return

		# Base values | Bázis értékek
		try:
			base_temp = float(prev_hour.get("temp") or 0)
			base_lux = float(prev_hour.get("lux") or 0)
			base_rain = float(prev_hour.get("rain") or 0)
			base_wind = float(prev_hour.get("wind") or 0)
		except Exception as e:
			Domoticz.Error(f"Invalid hourly weather value | Érvénytelen órás időjárásadat: {e}")
			self.now_outtemp = None
			self.now_lux = None
			self.now_rain = None
			self.now_wind = None
			return

		# Next hour values | Következő órás értékek
		if next_hour_data:
			try:
				next_temp = float(next_hour_data.get("temp", base_temp))
				next_lux = float(next_hour_data.get("lux", base_lux))
				next_rain = float(next_hour_data.get("rain", base_rain))
				next_wind = float(next_hour_data.get("wind", base_wind))
			except:
				next_temp = base_temp
				next_lux = base_lux
				next_rain = base_rain
				next_wind = base_wind
		else:
			next_temp = base_temp
			next_lux = base_lux
			next_rain = base_rain
			next_wind = base_wind

		# Interpolation factor | Interpoláció faktora
		factor = minute / 60.0

		# Linear interpolation | --- LIN. INTERPOLÁCIÓ ---
		self.now_outtemp = base_temp + (next_temp - base_temp) * factor
		self.now_rain = base_rain + (next_rain - base_rain) * factor
		self.now_wind = base_wind + (next_wind - base_wind) * factor

		# Nighttime lux correction | Éjszakai luxérték korrekciója
		self.now_lux = max(0.0, base_lux + (next_lux - base_lux) * factor)
		sunrise, sunset = self.get_sun_times()
		now_time = datetime.now().strftime("%H:%M")

		if sunrise and sunset and not (sunrise <= now_time <= sunset):
			self.now_lux = 0.0
			Domoticz.Debug("Nighttime detected, lux set to zero | Éjszakai időszak, luxérték nullázva")

		Domoticz.Debug((f"now_outtemp = {self.now_outtemp}") + ' | Mért vagy számított érték')
		Domoticz.Debug((f"now_lux = {self.now_lux}") + ' | Mért vagy számított érték')
		Domoticz.Debug((f"now_rain = {self.now_rain}") + ' | Mért vagy számított érték')
		Domoticz.Debug((f"now_wind = {self.now_wind}") + ' | Mért vagy számított érték')


	def LastSwitchTime(self, redonyidx):
		Domoticz.Debug((f"LastSwitchTime redonyidx: {redonyidx}") + ' | Mért vagy számított érték')

		device = DomoticzAPI(f"type=command&param=getlightlog&range=day&idx={redonyidx}")

		if not isinstance(device, dict) or "result" not in device:
			Domoticz.Error(f"Missing result in shutter log response | Hiányzó result mező a redőnynaplóban: {device}")
			return True
		if not isinstance(device["result"], list) or not device["result"]:
			Domoticz.Error("Shutter log empty or invalid | A redőnynapló üres vagy érvénytelen")
			return True

		def parse_time(entry):
			dateformat = "%Y-%m-%d %H:%M:%S"
			try:
				return time.mktime(time.strptime(entry["Date"], dateformat))
			except Exception as e:
				Domoticz.Error(f"Invalid date | Hibás dátum: {entry.get('Date', '?')} - {e}")
				return 0

		# Use only entries with valid timestamps | Csak az érvényes dátummal rendelkező bejegyzéseket használjuk
		valid_entries = [e for e in device["result"] if "Date" in e and e["Date"]]
		if not valid_entries:
			Domoticz.Error("No valid timestamp in shutter log | Nincs érvényes időbélyeg a redőnynaplóban")
			return True

		try:
			latest = max(valid_entries, key=parse_time)
		except Exception as e:
			Domoticz.Error(f"Cannot process shutter logs | A redőnynapló feldolgozása sikertelen: {e}")
			return True

		datestring = latest.get("Date")
		if not datestring:
			Domoticz.Error("Latest shutter log entry has no date | A legfrissebb redőnynapló-bejegyzésből hiányzik a dátum")
			return True

		Domoticz.Debug(f"Last shutter action time | Utolsó redőnymozgatás ideje: {datestring}")

		try:
			last_update_timestamp = time.mktime(time.strptime(datestring, "%Y-%m-%d %H:%M:%S"))
		except Exception as e:
			Domoticz.Error(f"Cannot parse date | A dátum feldolgozása sikertelen: {datestring}, hiba: {e}")
			return True

		now_timestamp = time.time()
		SwitchTime = (last_update_timestamp + 2 * 60) < now_timestamp

		Domoticz.Debug((f"LastSwitchTime = {SwitchTime}") + ' | Részletes naplóadat')
		return SwitchTime

	def addfavorite(self, deviceidx):
		self._fav_actions[deviceidx] = "add"

	def removefavorite(self, deviceidx):
		# csak akkor, ha erre az idx-re még nem volt ADD
		if self._fav_actions.get(deviceidx) != "add":
			self._fav_actions[deviceidx] = "remove"

	def applyfavorites(self):

		Domoticz.Debug(
			"applyfavorites(): _fav_actions = {}".format(self._fav_actions)
		)

		for idx, action in self._fav_actions.items():
			if action == "add":
				DomoticzAPI(
					"idx={}&isfavorite=1&param=makefavorite&type=command".format(idx)
				)
			elif action == "remove":
				DomoticzAPI(
					"idx={}&isfavorite=0&param=makefavorite&type=command".format(idx)
				)

		# reset következő ciklusra
		self._fav_actions.clear()


global _plugin
_plugin = BasePlugin()


def onStart():
	global _plugin
	_plugin.onStart()


def onStop():
	global _plugin
	_plugin.onStop()


def onCommand(Unit, Command, Level, Color):
	global _plugin
	_plugin.onCommand(Unit, Command, Level, Color)


def onHeartbeat():
	global _plugin
	_plugin.onHeartbeat()


# Plugin utility functions | Plugin utility functions ---------------------------------------------------

def parseCSV(strCSV):

	listvals = []
	for value in strCSV.split(","):
		try:
			val = int(value)
		except:
			pass
		else:
			listvals.append(val)
	return listvals

def parseCSVparams(strCSV):

	listvalsparams = []
	for value in strCSV.split(","):
		try:
			val = int(value)
		except:
			pass
		else:
			listvalsparams.append(val)
	return listvalsparams

def parseCSVparamslist(strCSV):

	listvalsparams = []
	i=0
	for value in strCSV.split(","):
		try:
			if i in (2,3):
				val = str(value)
			else:
				val = int(value)
		except:
			pass
		else:
			listvalsparams.append(val)
		i+=1
	return listvalsparams

def parse_sensor_ids(strCSV, sensor_type):
	result = []
	current_type = None

	for item in strCSV.split(","):
		item = item.strip()

		if ":" in item:
			prefix, value = item.split(":", 1)
			current_type = prefix.strip().upper()
		else:
			value = item

		if current_type == sensor_type and value.strip().isdigit():
			result.append(int(value.strip()))

	return result


def parse_B(strCSV):
	return parse_sensor_ids(strCSV, "B")


def parse_K(strCSV):
	return parse_sensor_ids(strCSV, "K")


def parse_F(strCSV):
	return parse_sensor_ids(strCSV, "F")


def parse_S(strCSV):
	return parse_sensor_ids(strCSV, "S")


def parse_V(strCSV):
	return parse_sensor_ids(strCSV, "V")

def DomoticzAPI(APICall):

	resultJson = None
	url = "http://{}:{}/json.htm?{}".format(Parameters["Address"], Parameters["Port"], parse.quote(APICall, safe="&="))
	Domoticz.Debug("Calling Domoticz API | Domoticz API hívása")
	try:
		req = request.Request(url)
		if Parameters["Username"] != "":
			Domoticz.Debug("Adding API authentication | API-hitelesítés beállítása: {}".format(Parameters["Username"]))
			credentials = ('%s:%s' % (Parameters["Username"], Parameters["Password"]))
			encoded_credentials = base64.b64encode(credentials.encode('ascii'))
			req.add_header('Authorization', 'Basic %s' % encoded_credentials.decode("ascii"))
		
		response = request.urlopen(req, timeout=10)
		if response.status == 200:
			resultJson = json.loads(response.read().decode('utf-8'))
			if resultJson["status"] != "OK":
				Domoticz.Error("Domoticz API error | Domoticz API-hiba, állapot = {}".format(resultJson["status"]))
				resultJson = None
		else:
			Domoticz.Error("Domoticz API HTTP error | Domoticz API HTTP-hiba = {}".format(response.status))
		response.close()
	except:
		Domoticz.Error("Domoticz API request failed | Domoticz API kérés sikertelen")
	return resultJson


# Generic helper functions | Segédfüggvény vagy számítás
def DumpConfigToLog():
	for x in Parameters:
		if Parameters[x] != "":
			value = "***" if x.lower() in ("password", "username") else str(Parameters[x])
			Domoticz.Debug(("'" + x + "':'" + value + "'") + ' | Részletes naplóadat')
	Domoticz.Debug(("Device count: " + str(len(Devices))) + ' | Mért vagy számított érték')
	for x in Devices:
		Domoticz.Debug(("Device: " + str(x) + " - " + str(Devices[x])) + ' | Mért vagy számított érték')
		Domoticz.Debug(("Device ID: '" + str(Devices[x].ID) + "'") + ' | Mért vagy számított érték')
		Domoticz.Debug(("Device Name: '" + Devices[x].Name + "'") + ' | Mért vagy számított érték')
		Domoticz.Debug(("Device nValue: " + str(Devices[x].nValue)) + ' | Mért vagy számított érték')
		Domoticz.Debug(("Device sValue: '" + Devices[x].sValue + "'") + ' | Mért vagy számított érték')
		Domoticz.Debug(("Device LastLevel: " + str(Devices[x].LastLevel)) + ' | Mért vagy számított érték')
	return


def JelenletAPI(jelennev):
	resultJelen = False  # Alapértelmezett érték
	
	try:
		wifiurl = "http://{}/cgi-bin/luci/wifi-presence/{}".format(Parameters["Address"], jelennev)
		Domoticz.Debug("Calling presence API (Wi-Fi) | Wi-Fi jelenlét API hívása: {}".format(wifiurl))
		reqwifi = request.Request(wifiurl)
		response = request.urlopen(reqwifi, timeout=5)
		
		if response.status == 404:
			Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): 404 error - URL not found | Az URL nem található")
			resultJelen = "404"
		elif response.status == 200:
			response_text = response.read().decode('utf-8').strip()
			Domoticz.Debug("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág) response: {}".format(response_text))  # Logoljuk a válasz tartalmát
			
			# Distinguish JSON and plain-text responses | Különbséget teszünk a JSON válasz és egyéb string válaszok között
			if response_text == "nogroup":
				resultJelen = "nogroup Wifi"
				Domoticz.Debug("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): Unknown presence group | Ismeretlen jelenlétcsoport")
			elif response_text:  # Ha nem üres a válasz, próbálkozunk JSON-nal
				try:
					resultJelen = json.loads(response_text)
				except json.JSONDecodeError:
					Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): Invalid JSON response | Érvénytelen JSON-válasz")
					resultJelen = False
				
				# Validate boolean response | Ellenőrizzük, hogy a válasz bool típusú-e
				if isinstance(resultJelen, bool):
					Domoticz.Debug("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): Boolean response | Logikai válasz érkezett")
				elif isinstance(resultJelen, str):
					if resultJelen.strip() == "true":
						resultJelen = True
					elif resultJelen.strip() == "false":
						resultJelen = False
				else:
					Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): Unexpected response type | Váratlan válasstípus")
			else:
				Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): Empty response | Üres válasz érkezett")
		else:
			Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): HTTP error | HTTP-hiba = {}".format(response.status))
		response.close()

	except request.HTTPError as e:
		if e.code == 404:
			Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): 404 error - URL not found | Az URL nem található")
			resultJelen = "404"
		else:
			Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): HTTP error | HTTP-hiba = {}".format(e.code))
	except Exception as e:
		Domoticz.Error("Presence API (Wi-Fi) | Jelenlét API (Wi-Fi ág): Error calling '{}': {}".format(wifiurl, str(e)))

	# Separate Wi-Fi and LAN presence requests | Késleltetés, hogy a Wi-Fi és LAN ágak ne fussanak egyszerre
	time.sleep(0.2)

	# Try LAN presence if Wi-Fi did not detect presence | Ha az első próbálkozás nem adott 'True' értéket, próbálkozunk a második URL-lel
	if resultJelen is not True:
		try:
			lanurl = "http://{}/cgi-bin/luci/presence/{}".format(Parameters["Address"], jelennev)
			Domoticz.Debug("Calling presence API (LAN) | LAN jelenlét API hívása: {}".format(lanurl))
			reqlan = request.Request(lanurl)
			response = request.urlopen(reqlan, timeout=5)

			if response.status == 404:
				Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): 404 error - URL not found | Az URL nem található")
				resultJelen = "404"
			elif response.status == 200:
				response_text = response.read().decode('utf-8').strip()
				Domoticz.Debug("Presence API (LAN) | Jelenlét API (LAN ág) response: {}".format(response_text))  # Logoljuk a válasz tartalmát
				
				# Distinguish JSON and plain-text responses | Különbséget teszünk a JSON válasz és egyéb string válaszok között
				if response_text == "nogroup":
					resultJelen = "nogroup LAN"
					Domoticz.Debug("Presence API (LAN) | Jelenlét API (LAN ág): Unknown presence group | Ismeretlen jelenlétcsoport")
				elif response_text:  # Ha nem üres a válasz, próbálkozunk JSON-nal
					try:
						resultJelen = json.loads(response_text)
					except json.JSONDecodeError:
						Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): Invalid JSON response | Érvénytelen JSON-válasz")
						resultJelen = False
					
					# Validate boolean response | Ellenőrizzük, hogy a válasz bool típusú-e
					if isinstance(resultJelen, bool):
						Domoticz.Debug("Presence API (LAN) | Jelenlét API (LAN ág): Boolean response | Logikai válasz érkezett")
					elif isinstance(resultJelen, str):
						if resultJelen.strip() == "true":
							resultJelen = True
						elif resultJelen.strip() == "false":
							resultJelen = False
					else:
						Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): Unexpected response type | Váratlan válasstípus")
				else:
					Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): Empty response | Üres válasz érkezett")
			else:
				Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): HTTP error | HTTP-hiba = {}".format(response.status))
			response.close()

		except request.HTTPError as e:
			if e.code == 404:
				Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): 404 error - URL not found | Az URL nem található")
				resultJelen = "404"
			else:
				Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): HTTP error | HTTP-hiba = {}".format(e.code))
		except Exception as e:
			Domoticz.Error("Presence API (LAN) | Jelenlét API (LAN ág): Error calling '{}': {}".format(lanurl, str(e)))

	return resultJelen


def to_timestamp(date_string):
	"""
	Convert date string to timestamp.
	:param date_string: str - Date in 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD' format
	:return: float - Timestamp or None if invalid
	"""
	formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]  # Támogatott formátumok
	for fmt in formats:
		try:
			struct_time = time.strptime(date_string, fmt)
			return time.mktime(struct_time)  # Convert to timestamp
		except ValueError:
			continue
	Domoticz.Error(f"Invalid date format | Érvénytelen dátumformátum: {date_string}")
	return None