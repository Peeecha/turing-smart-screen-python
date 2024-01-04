import os, sys, time
from ctypes import *
from shutil import copyfile
from typing import Tuple
import math
import os
import copy
from statistics import mean

import struct
from multiprocessing import shared_memory

import construct as cstruct
from construct import Struct, Int32un, Long

import library.sensors.sensors as sensors
from library.log import logger


memory = shared_memory.SharedMemory('Global\\HWiNFO_SENS_SM2')
decoded_memory_data = []

def refresh_data_from_memory():
    global decoded_memory_data, memory
    
    decoded_memory_data.clear()
 
    # size = 44
    sensor_element_struct = Struct(
        'dwSignature' / Int32un,
        'dwVersion' / Int32un,
        'dwRevision' / Int32un,
        'poll_time' / Long,
        'dwOffsetOfSensorSection' / Int32un,
        'dwSizeOfSensorElement' / Int32un,
        'dwNumSensorElements' / Int32un,
        'dwOffsetOfReadingSection' / Int32un,
        'dwSizeOfReadingElement' / Int32un,
        'dwNumReadingElements' / Int32un,
    )
    
    sensor_element = sensor_element_struct.parse(memory.buf[0:Struct.sizeof(sensor_element_struct)])
    # print(sensor_element)
    
    reading_element_struct = Struct(
        'tReading' / cstruct.Int32un,
        'dwSensorIndex' / cstruct.Int32un,
        'dwReadingID' / cstruct.Int32un,
        'szLabelOrig' / cstruct.PaddedString(128, encoding='utf-8'),
        'szLabelUser' / cstruct.PaddedString(128, encoding='utf-8'),
        'szUnit' / cstruct.PaddedString(16, encoding='utf-8'),
        'Value' / cstruct.Double,
        'ValueMin' / cstruct.Double,
        'ValueMax' / cstruct.Double,
        'ValueAvg' / cstruct.Double
    )
    
    # fmt = '=III128s128s16sdddd'
    # reading_element_struct = struct.Struct(fmt)
    offset = sensor_element.dwOffsetOfReadingSection
    length = sensor_element.dwSizeOfReadingElement
    
    for index in range(sensor_element.dwNumReadingElements):
        data_start = offset + index * length
        data_end = offset + (index + 1) * length
        raw_data = memory.buf[data_start:data_end]
    
        # Extract the fields manually from raw_data
        tReading, dwSensorIndex, dwReadingID = struct.unpack("III", raw_data[:12])
        szLabelOrig = raw_data[12:140]
        szLabelUser = raw_data[140:268]
        szUnit = raw_data[268:284]
        Value, ValueMin, ValueMax, ValueAvg = struct.unpack("dddd", raw_data[284:316])

        # Convert bytes to string and remove null bytes
        szLabelOrig_decoded = memory.buf[offset + index * length + 12: offset + index * length + 140].tobytes().decode('utf-8', errors='ignore').rstrip('\x00')
        szLabelUser_decoded = memory.buf[offset + index * length + 140: offset + index * length + 268].tobytes().decode('utf-8', errors='ignore').rstrip('\x00')
        szUnit_decoded = memory.buf[offset + index * length + 268: offset + index * length + 284].tobytes().decode('utf-8', errors='ignore').rstrip('\x00')
    
        # Print the decoded and cleaned strings
        #print(tReading, dwSensorIndex, dwReadingID)
        #print(f"szLabelOrig (decoded): {szLabelOrig_decoded}")
        #print(f"szLabelUser (decoded): {szLabelUser_decoded}")
        #print(f"szUnit (decoded): {szUnit_decoded}")
        #print(Value, ValueMin, ValueMax, ValueAvg)
        #print("----------------------------------")
        
        # Append decoded data to a list 
        decoded_memory_data.append({
            "szLabelOrig": szLabelOrig_decoded,
            "szLabelUser": szLabelUser_decoded,
            "szUnit": szUnit_decoded,
            "Value": float(Value),
            "ValueMin": float(ValueMin),
            "ValueMax": float(ValueMax),
            "ValueAvg": float(ValueAvg)
        })
            

def get_sensor_value(sensor_name) -> float:
    global decoded_memory_data
    
    for data in decoded_memory_data:
        if data['szLabelOrig'].startswith(sensor_name):
            return float(data['Value'])
        
    return math.nan
    
    
def get_sensor_value_additive(sensor_name) -> float:
    global decoded_memory_data
    
    total = 0
    for data in decoded_memory_data:
        if data['szLabelOrig'].startswith(sensor_name):
            total = total + float(data['Value'])
        
    return total
  
        
class Cpu(sensors.Cpu):
    @staticmethod
    def percentage(interval: float) -> float:
        if interval > 0:
            refresh_data_from_memory()
        
        return get_sensor_value('Total CPU Usage')

    @staticmethod
    def frequency() -> float:
        frequencies = []
        
        for i in range(99):  # try to fetch up to 100 cores, increase if needed
            freq = get_sensor_value("Core {} Clock".format(i))
            if not math.isnan(freq): 
                frequencies.append(freq)
            else:
                break 
                
        if frequencies:
            # Take mean of all core clock as "CPU clock" (as it is done in Windows Task Manager Performance tab)
            return mean(frequencies)
        else:
            # Frequencies reading is not supported on this CPU
            return math.nan

    @staticmethod
    def load() -> Tuple[float, float, float]:  # not implemented, returns current load (%) instead:
        load_values = []
        
        percentage = get_sensor_value('Total CPU Usage')
        load_values.append(percentage)
        load_values.append(percentage)
        load_values.append(percentage)

        return load_values

    @staticmethod
    def is_temperature_available() -> bool:
        return True

    @staticmethod
    def temperature() -> float:
        return get_sensor_value('CPU (Tctl/Tdie)')

    @staticmethod
    def power() -> float:
        return get_sensor_value('CPU Package Power')

class Gpu(sensors.Gpu):
    @classmethod
    def stats(cls) -> Tuple[float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / temp (°C)
        load = get_sensor_value('GPU Utilization')
        used_mem = get_sensor_value('GPU Memory Usage')
        total_mem = math.nan
        temp = get_sensor_value('GPU Temperature')

        return load, (used_mem / total_mem * 100.0), used_mem, temp

    @classmethod
    def fps(cls) -> int:
        return get_sensor_value('Framerate (Displayed)')

    @classmethod
    def is_available(cls) -> bool:      
        return True


class Memory(sensors.Memory):
    @staticmethod
    def swap_percent() -> float:

        virtual_mem_used = int(get_sensor_value('Virtual Memory Committed'))
        mem_used = int(get_sensor_value('Physical Memory Used'))
        virtual_mem_available = int(get_sensor_value('Virtual Memory Available'))
        mem_available = int(get_sensor_value('Physical Memory Available'))

        # Compute swap stats from virtual / physical memory stats
        swap_used = virtual_mem_used - mem_used
        swap_available = virtual_mem_available - mem_available
        swap_total = swap_used + swap_available

        return swap_used / swap_total * 100.0

    @staticmethod
    def virtual_percent() -> float:
        return get_sensor_value('Physical Memory Load')

    @staticmethod
    def virtual_used() -> int:  # In bytes
        return get_sensor_value('Virtual Memory Committed') * 1000000000.0

    @staticmethod
    def virtual_free() -> int:  # In bytes
        return get_sensor_value('Virtual Memory Available') * 1000000000.0



class Disk(sensors.Disk):
    @staticmethod
    def disk_usage_percent() -> float:
        return 0

    @staticmethod
    def disk_used() -> int:  # In bytes
        used = 0

        return used

    @staticmethod
    def disk_free() -> int:  # In bytes
        free = 0

        return free


class Net(sensors.Net):
    @staticmethod
    def stats(if_name, interval) -> Tuple[
        int, int, int, int]:  # up rate (B/s), uploaded (B), dl rate (B/s), downloaded (B)

        upload_rate = int(get_sensor_value_additive('Current UP rate'))
        uploaded = int(get_sensor_value('Total UP'))
        download_rate = int(get_sensor_value_additive('Current DL rate'))
        downloaded = int(get_sensor_value('Total DL'))

        return upload_rate, uploaded, download_rate, downloaded
