from inspect import isgenerator
from sys import stdout
import python_weather
import asyncio
import os

import library.sensors.sensors as sensors
from typing import Tuple

client = None

async def getweather(city, locale):
  default_locale = python_weather.Locale.ENGLISH
  try:
    default_locale = python_weather.Locale[locale]
  except KeyError:
    print(f"No matching enum locale found for string: {locale}. Using default ENGLISH.")
  
  try:  
    async with python_weather.Client(unit=python_weather.METRIC, locale=default_locale) as client:  # python_weather.Locale.CZECH
      # fetch a weather forecast from a city
      client = await client.get(city)
        #☁️🌫🌧❄️🌦🌧⛅️☀️🌩⛈✨ 
      return client.current.kind.emoji, client.current.temperature, client.current.description  # Return the weather data
  except:
    return '🌡️', '', 'NO DATA'
  
    
#   print(client.current.kind.emoji)
#   
#   # returns the current day's forecast temperature (int)
#   print(client.current.temperature)
#   
#   # get the weather forecast for a few days
#   for forecast in client.forecasts:
#     print(forecast)
#     
#     # hourly forecasts
#     for hourly in forecast.hourly:
#       print(f' --> {hourly!r}')


async def get_weather_and_update(city, locale, callback):
    weather_data = await getweather(city, locale)
    
    callback(weather_data)


class Forecast(sensors.Forecast):
    @staticmethod
    def request(city, locale, callback): 
        loop = asyncio.new_event_loop()  # Create a new event loop
        asyncio.set_event_loop(loop)  # Set the event loop for the current thread
        try:
            loop.run_until_complete(get_weather_and_update(city, locale, callback))  # Run the async function with the loop
        finally:
            loop.close()  # Close the loop when done

