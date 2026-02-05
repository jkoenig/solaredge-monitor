#!/usr/bin/python
# -*- coding:utf-8 -*-
debug = False

import logging
import requests
import datetime
import sys
import os
import time
import traceback

import datetime as dt
from PIL import Image,ImageDraw,ImageFont

fontsdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fonts')
debugdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'debug')
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')

if os.path.exists(libdir):
    sys.path.append(libdir)

logging.basicConfig(level=logging.DEBUG)

# TODO: Phase 2 will extract these to environment variables
api_key = "YOUR_API_KEY"
site_id = "YOUR_SITE_ID"
sleep_timer = 180 # wait 3 minutes (180 secunds) before updating power flow info from API
scale_factor = 4  # Skaliere das Bild um das 4-fache
original_width, original_height = 250, 122 # display size


    
icon_path = os.path.join(os.getcwd() + "/fonts/", f'FontAwesome6-Free-Solid-900.otf')
font_path_bold = os.path.join(os.getcwd() + "/fonts/", f'ArialBlack.ttf')
font_path = os.path.join(os.getcwd() + "/fonts/", f'Arial.ttf')
icon = ImageFont.truetype(icon_path, 20 * scale_factor) 
font10 = ImageFont.truetype(font_path, 16 * scale_factor)   
font14 = ImageFont.truetype(font_path_bold, 14 * scale_factor)   
font18 = ImageFont.truetype(font_path_bold, 18 * scale_factor) 
font24 = ImageFont.truetype(font_path_bold, 18 * scale_factor)
font28 = ImageFont.truetype(font_path_bold, 40 * scale_factor)
font30 = ImageFont.truetype(font_path_bold, 50 * scale_factor)  

meter_icon_left_postion = 225
meter_icon_top_postion = 1

subline_left_postion = 42

def get_site_overview():
    try:   
        logging.info("Invoke SolarEdge API to get overview data") 
        api_url = "https://monitoringapi.solaredge.com/site/" + site_id + "/overview?api_key=" + api_key
        response = requests.get(api_url)
        if response.status_code == 200:
            if debug:
                with open("debug/solaredge-site-overview-results.txt", "a") as file:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    file.write(f"{timestamp}: {response.text}\n")
                logging.info(f"Data saved at {timestamp}")
            
            data = response.json()
            
            lastUpdateTime = data["overview"]["lastUpdateTime"]
            lifeTimeEnergy = round(float(data["overview"]["lifeTimeData"]["energy"]/1000/1000),2)
            lifeTimeRevenue = round(data["overview"]["lifeTimeData"]["revenue"],2)
            lastYearEnergy = int(round(float(data["overview"]["lastYearData"]["energy"]/1000),0))
            pricePerKwh = round(lifeTimeRevenue/(lifeTimeEnergy*1000),2)
            lastYearRevenue = round(lastYearEnergy*pricePerKwh, 2)
            lastMonthEnergy = int(round(float(data["overview"]["lastMonthData"]["energy"])/1000,0))
            lastMonthRevenue = round(lastMonthEnergy*pricePerKwh, 2)
            lastDayEnergy = round(float(data["overview"]["lastDayData"]["energy"])/1000,2)
            lastDayRevenue = round(lastDayEnergy*pricePerKwh, 2)
            currentPowerConsumption = round(float(data["overview"]["currentPower"]["power"])/1000,2)
            
            results = [
                lastUpdateTime,
                lifeTimeEnergy,
                lifeTimeRevenue,
                lastYearEnergy,
                lastYearRevenue,
                lastMonthEnergy,
                lastMonthRevenue,
                lastDayEnergy,
                lastDayRevenue,
                currentPowerConsumption
            ]
           
            logging.info(f"Last Update Time: {lastUpdateTime}")
            logging.info(f"------ Site Overview - Energy Production ----------")
            logging.info(f"Life Time Energy: {lifeTimeEnergy} MWh")
            logging.info(f"Life Time Revenue: {lifeTimeRevenue} CHF (assuming all fed-in)")
            logging.info(f"Last Year Energy: {lastYearEnergy} kWh (rounded)")
            logging.info(f"Last Year Revenue: {lastYearRevenue} CHF (assuming all fed-in)")
            logging.info(f"Last Month Energy: {lastMonthEnergy} kWh (rounded)")
            logging.info(f"Last Month Revenue: {lastMonthRevenue} CHF (assuming all fed-in)")
            logging.info(f"Last Day Energy: {lastDayEnergy} kWh")
            logging.info(f"Last Day Revenue: {lastDayRevenue} CHF (assuming all fed-in)")
            logging.info(f"Current Power: {currentPowerConsumption} kW (don't know what this meter stands for, it submits false readings)")
        else:
            print(f"Error calling API. Status code: {response.status_code}")
            
        return results
    except Exception as e:
        print(f"An error occurred: {e}")    
        
def get_energy_details():

    try:   
        logging.info("Invoke SolarEdge API to get energy detail data")  
        today = datetime.date.today().strftime("%Y-%m-%d")
        api_url = "https://monitoringapi.solaredge.com/site/"+site_id+"/energyDetails?meters=Purchased,FeedIn,Production,SelfConsumption,Consumption&startTime="+today+"%2000:00:00&endTime="+today+"%2023:59:00&api_key="+api_key
        response = requests.get(api_url)
        if response.status_code == 200:
            if debug:
                with open("debug/solaredge-energyDetails-results.txt", "a") as file:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    file.write(f"{timestamp}: {response.text}\n")
                logging.info(f"Data saved at {timestamp}")
            
        data = response.json()
        
        self_consumption = None
        consumption = None
        production = None
        feed_in = None
        purchased = None
        
        # Durchlaufe alle Meter-Typen
        for meter in data['energyDetails']['meters']:
            if meter['type'] == 'SelfConsumption':
                self_consumption = float(meter['values'][0]['value'])
            elif meter['type'] == 'Consumption':
                consumption = float(meter['values'][0]['value'])
            elif meter['type'] == 'Production':
                production = float(meter['values'][0]['value'])    
            elif meter['type'] == 'Purchased':
                purchased = float(meter['values'][0]['value'])
            elif meter['type'] == 'FeedIn':
                feed_in = float(meter['values'][0]['value'])        
         
        consumption = round(float(consumption)/1000,2)
        self_consumption = round(float(self_consumption)/1000,2)
        production = round(float(production)/1000,2)
        feed_in = round(float(feed_in)/1000,2)
        purchased = round(float(purchased)/1000,2)
        
        self_consumption_percentage = round(self_consumption*100/production,2)
        feed_in_percentage = round(feed_in*100/production,2)
        self_production_percentage = round(self_consumption*100/consumption,2)
        purchased_percentage = round(purchased*100/consumption,2)
        
        results = [
            self_consumption,
            consumption,
            production,
            feed_in,
            purchased
        ]
                   
        logging.info(f"------ Today's Energy Details ------")
        logging.info(f"Total Production: {production} kWh")
        logging.info(f" -> {self_consumption} kWh Self Consumption ({self_consumption_percentage} %)")
        logging.info(f" -> {feed_in} kWh Feed In ({feed_in_percentage} %)")
        logging.info(f"Total Consumption: {consumption} kWh")
        logging.info(f" -> {purchased} kWh Purchased ({purchased_percentage} %)")
        logging.info(f" -> {self_consumption} kWh From Self Production ({self_production_percentage} %)")


        return results
    except Exception as e:
        print(f"An error occurred: {e}")        
        
def get_current_power_flow():
    try:
        logging.info("Invoke SolarEdge API to get current power flow data") 
        api_url = "https://monitoringapi.solaredge.com/site/" + site_id + "/currentPowerFlow?api_key=" + api_key
        response = requests.get(api_url)
        if response.status_code == 200:
            with open("debug/solaredge-currentPowerFlow-results.txt", "a") as file:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file.write(f"{timestamp}: {response.text}\n")
            logging.info(f"Data saved at {timestamp}")
            
            response_data = response.json()
            
            connections = response_data["siteCurrentPowerFlow"]["connections"]
            grid_current_power = response_data["siteCurrentPowerFlow"]["GRID"]["currentPower"] # either purchase or sale
            load_current_power = response_data["siteCurrentPowerFlow"]["LOAD"]["currentPower"]
            pv_current_power = response_data["siteCurrentPowerFlow"]["PV"]["currentPower"]
            storage_status = response_data["siteCurrentPowerFlow"]["STORAGE"]["status"]
            storage_current_power = response_data["siteCurrentPowerFlow"]["STORAGE"]["currentPower"]
            state_of_charge = response_data["siteCurrentPowerFlow"]["STORAGE"]["chargeLevel"]
            off_grid = False
            
            logging.info(f"------ Current Energy Details -----")
            for connection in connections:
                from_device = connection["from"]
                to_device = connection["to"]
                
                if from_device.lower() == "grid":
                    logging.info(f"ON Grid: Currently purchasing {grid_current_power} kW.") 
                    break
                
                if from_device.lower() != "grid":    
                    logging.info(f"OFF Grid: Powering from {from_device}") 
                    off_grid = True
                    
                if to_device.lower() == "grid":
                    logging.info(f"OFF Grid: Currently feeding in {grid_current_power} kW.")       
                    break   
            
            logging.info(f"Current consumption is {load_current_power} kW and PV production is {pv_current_power} kW.")
            logging.info(f"Battery is {storage_status.lower()} with {storage_current_power} kW. SoC is {state_of_charge} %.")
            
            results = [
                grid_current_power,
                load_current_power,
                pv_current_power,
                storage_status,
                storage_current_power,
                state_of_charge,
                off_grid
            ]
            
            return results
        else:
            logging.info(f"Error calling API. Status code: {response.status_code}")
    except Exception as e:
        logging.info(f"An error occurred: {e}")

def display(energy_details):
    global original_width, original_height
    try:
        if debug == False:
            try:
                from waveshare_epd import epd2in13_V3
                logging.info("Waveshare EPD Modul erfolgreich importiert")
                epd = epd2in13_V3.EPD()
                logging.info("Init and clear")
                epd.init()
                epd.Clear(0xFF)
                original_width, original_height = epd.height, epd.width
            except ModuleNotFoundError as e:
                logging.error(f"Fehler beim Importieren des Waveshare EPD Moduls: {e}")
                return
              
        bar_chart_width = 140 # 140 px

        # Höher aufgelöstes Bild erstellen
        high_res_width = original_width * scale_factor
        high_res_height = original_height * scale_factor
        high_res_image = Image.new('RGB', (high_res_width, high_res_height), color=(255, 255, 255)) # 255: clear the frame   

        draw = ImageDraw.Draw(high_res_image)
    
        draw.text((1 * scale_factor, 1 * scale_factor), str(energy_details[2]), font=font24, fill=0)
        draw.text((16 * scale_factor, 29 * scale_factor), "Produktion", font=font10, fill=0)
        
        # calcuate the with of 2 parts of the bar chart
        self_consumption_percentage = round((energy_details[0] * bar_chart_width)/energy_details[2],0)
        feed_in_percentage = bar_chart_width-self_consumption_percentage
        
        # define start and endpoint of the first bar chart part
        top_left = (92 * scale_factor, 20 * scale_factor)
        bottom_right = ((92 + self_consumption_percentage) * scale_factor, 28 * scale_factor)
        
        draw.rectangle([top_left, bottom_right], fill=(0, 0, 0))
        
        # define start and endpoint of the second bar chart part, positioned right after the first part
        top_left = (bottom_right[0], 20 * scale_factor)
        bottom_right = ((92 * scale_factor) + (bar_chart_width * scale_factor), 28 * scale_factor)
        
        draw.rectangle([top_left, bottom_right], fill=(255, 255, 255), outline=(0, 0, 0))
        
        draw.text((92 * scale_factor, 30 * scale_factor), str(energy_details[0]) + " kWh", font=font14, fill=0)
        draw.text((92 * scale_factor, 45 * scale_factor), "Genutzt", font=font10, fill=0)
        
        draw.text((175 * scale_factor, 30 * scale_factor), str(energy_details[3]) + " kWh", font=font14, fill=0)
        draw.text((175 * scale_factor, 45 * scale_factor), "Ins Netz", font=font10, fill=0)
 
        draw.line([(1 * scale_factor, 61  * scale_factor), (254 * scale_factor, 61  * scale_factor)], fill=0, width=1)
        
        draw.text((1 * scale_factor, 62 * scale_factor), str(energy_details[1]), font=font24, fill=0)
        draw.text((16 * scale_factor, 91 * scale_factor), "Verbrauch", font=font10, fill=0)
        
        # calcuate the with of 2 parts of the bar chart
        self_production_percentage = round((energy_details[4] * bar_chart_width)/energy_details[1],0)
        purchased_percentage = bar_chart_width-self_production_percentage
        
         # define start and endpoint of the first bar chart part
        top_left = (92 * scale_factor, 81 * scale_factor)
        bottom_right = ((92 + self_production_percentage) * scale_factor, 89 * scale_factor)
                
        draw.rectangle([top_left, bottom_right], fill=(0, 0, 0))
        
         # define start and endpoint of the second bar chart part, positioned right after the first part
        top_left = (bottom_right[0], 81 * scale_factor)
        bottom_right = ((92 * scale_factor) + (bar_chart_width * scale_factor), 89 * scale_factor)
        
        draw.rectangle([top_left, bottom_right], fill=(255, 255, 255), outline=(0, 0, 0))
        
        draw.text((92 * scale_factor, 91 * scale_factor), str(energy_details[4]) + " kWh", font=font14, fill=0)
        draw.text((92 * scale_factor, 106 * scale_factor), "Vom Netz", font=font10, fill=0)
        
        draw.text((175 * scale_factor, 91 * scale_factor), str(energy_details[0]) + " kWh", font=font14, fill=0)
        draw.text((175 * scale_factor, 106 * scale_factor), "Von Sonne", font=font10, fill=0)

        image = high_res_image.resize((original_width, original_height), Image.LANCZOS)
         
        if debug == False:
            epd.display(epd.getbuffer(image))
            time.sleep(2)
        else: 
            image.show()
            image.save("display/2-13inch-EInk-overview.png")
        
    except Exception as e:
        logging.info(f"An error occurred: {e}")    

# display centered info for "Hausakku"        
def display2(power_flow):
    global original_width, original_height
    try:
        if debug == False:
            try:
                from waveshare_epd import epd2in13_V3
                logging.info("Waveshare EPD Modul erfolgreich importiert")
                epd = epd2in13_V3.EPD()
                logging.info("Init and clear")
                epd.init()
                epd.Clear(0xFF)
                original_width, original_height = epd.height, epd.width
            except ModuleNotFoundError as e:
                logging.error(f"Fehler beim Importieren des Waveshare EPD Moduls: {e}")
                return
            
        state_of_charge = power_flow[5]
        
        # Index 0: 0 bis < 25
        # Index 1: 25 bis < 50
        # Index 2: 50 bis < 75
        # Index 3: 75 bis < 100
        # Index 4: 100
        battery_levels = ["\uF244", "\uF243", "\uF242", "\uF241", "\u1F50B"]
        index = int(state_of_charge / (100 / (len(battery_levels) - 1)))
     
         # TODO: 100% icon does not work, when index = 4
        
        high_res_width = original_width * scale_factor
        high_res_height = original_height * scale_factor
        high_res_image = Image.new('RGB', (high_res_width, high_res_height), color=(255, 255, 255)) # 255: clear the frame   

        draw = ImageDraw.Draw(high_res_image)
        
        draw.text((1 * scale_factor, 1 * scale_factor), "Hausakku", font=font10, fill=0)
        
        draw.text((meter_icon_left_postion * scale_factor, meter_icon_top_postion * scale_factor), battery_levels[index], font=icon, fill=(0,0,0)) 
        
        text1 = str(power_flow[5]) + "%"
        
        text1_bbox = draw.textbbox((0, 0), text1, font=font30)
        text1_width = text1_bbox[2] - text1_bbox[0]
        text1_height = text1_bbox[3] - text1_bbox[1]
        
        # Positionen berechnen, um den Text zu zentrieren
        text1_x = (high_res_width - text1_width) / 2
        text1_y = (high_res_height - text1_height) / 6
        
        draw.text((text1_x, text1_y), text1, font=font30, fill=0)

        if str(power_flow[3]).lower() != "idle":
            text2 = str(power_flow[4]) + " kW " + str(power_flow[3])
            text2_bbox = draw.textbbox((0, 0), text2, font=font14)
            text2_width = text2_bbox[2] - text2_bbox[0]        
            # Positionen berechnen, um den Text zu zentrieren
            text2_x = (high_res_width - text2_width) / 2
            draw.text((text2_x, 300), text2, font=font14, fill=0)   
        
        image = high_res_image.resize((original_width, original_height), Image.LANCZOS)
         
        if debug == False:
            epd.display(epd.getbuffer(image))
            time.sleep(2)
        else: 
            image.show() 
            image.save("display/2-13inch-EInk-power-flow.png")
    
    except Exception as e:
        logging.info(f"An error occurred: {e}")                   

# display centered info for ON vs OFF Grid    
def display3(power_flow):
    global original_width, original_height
    try:
        if debug == False:
            try:
                from waveshare_epd import epd2in13_V3
                logging.info("Waveshare EPD Modul erfolgreich importiert")
                epd = epd2in13_V3.EPD()
                logging.info("Init and clear")
                epd.init()
                epd.Clear(0xFF)
                original_width, original_height = epd.height, epd.width
            except ModuleNotFoundError as e:
                logging.error(f"Fehler beim Importieren des Waveshare EPD Moduls: {e}")
                return
            
        off_grid = power_flow[6]
        
        # Index 0: on grid
        # Index 1: off grid
        grid_levels = ["\uE55B", "\uE560"]
        index = 1 if off_grid else 0

        high_res_width = original_width * scale_factor
        high_res_height = original_height * scale_factor
        high_res_image = Image.new('RGB', (high_res_width, high_res_height), color=(255, 255, 255)) # 255: clear the frame 
        
        draw = ImageDraw.Draw(high_res_image)
        
        draw.text((1 * scale_factor, 1 * scale_factor), "Netzanschluss", font=font10, fill=0)
        
        draw.text((meter_icon_left_postion * scale_factor, meter_icon_top_postion * scale_factor), grid_levels[index], font=icon, fill=(0,0,0)) 
        
        if off_grid:
            text1 = "OFF GRID"
        else:
            text1 = "ON GRID"
        
        text1_bbox = draw.textbbox((0, 0), text1, font=font28)
        text1_width = text1_bbox[2] - text1_bbox[0]
        text1_height = text1_bbox[3] - text1_bbox[1]
        
        # Positionen berechnen, um den Text zu zentrieren
        text1_x = (high_res_width - text1_width) / 2
        text1_y = (high_res_height - text1_height) / 4  
        
        draw.text((text1_x, text1_y), text1, font=font28, fill=0)
        
        text2 = str(power_flow[1]) + " kW Consumption"
        text2_bbox = draw.textbbox((0, 0), text2, font=font14)
        text2_width = text2_bbox[2] - text2_bbox[0]        
        # Positionen berechnen, um den Text zu zentrieren
        text2_x = (high_res_width - text2_width) / 2
        draw.text((text2_x, 300), text2, font=font14, fill=0)
        
        image = high_res_image.resize((original_width, original_height), Image.LANCZOS)
         
        if debug == False:
            epd.display(epd.getbuffer(image))
            time.sleep(2)
        else: 
            image.show() 
            image.save("display/2-13inch-EInk-grid-state.png")
    
    except Exception as e:
        logging.info(f"An error occurred: {e}")

if __name__ == "__main__":
    logging.info("SolarEdge Monitor started ...")

    functions = [
        lambda: display3(get_current_power_flow()),
        lambda: display2(get_current_power_flow()),
        lambda: display(get_energy_details()),
    ]

    while True:
            current_hour = dt.datetime.now().hour
            if 6 <= current_hour < 24:
                for func in functions:
                    func()
                    time.sleep(sleep_timer)
            else:
                time.sleep(sleep_timer)             