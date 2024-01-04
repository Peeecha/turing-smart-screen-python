# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/

# Copyright (C) 2021-2023  Matthieu Houdebine (mathoudebine)
# Copyright (C) 2022-2023  Rollbacke
# Copyright (C) 2022-2023  Ebag333
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import sched
import threading
import time
from datetime import timedelta
from functools import wraps

import library.config as config
import library.stats as stats

STOPPING = False

# Function to run the event loop for a specific thread
def event_loop_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Dictionary to map thread names to event loops
thread_loops = {}

def async_job(threadname=None):
    """ wrapper to handle asynchronous threads """

    def decorator(func):
        """ Decorator to extend async_func """

        @wraps(func)
        def async_func(*args, **kwargs):
            """ create an asynchronous function to wrap around our thread """
            func_hl = threading.Thread(target=func, name=threadname, args=args, kwargs=kwargs)
            # Set up an event loop for the thread if not already present
            if threadname not in thread_loops:
                thread_loops[threadname] = threading.Thread(target=event_loop_thread, name=f"{threadname}_Loop")
                thread_loops[threadname].start()
            func_hl.start()

            return func_hl

        return async_func

    return decorator


def schedule(interval):
    """ wrapper to schedule asynchronous threads """

    def decorator(func):
        """ Decorator to extend periodic """

        def periodic(scheduler, periodic_interval, action, actionargs=()):
            """ Wrap the scheduler with our periodic interval """
            global STOPPING
            if not STOPPING:
                # If the program is not stopping: re-schedule the task for future execution
                scheduler.enter(periodic_interval, 1, periodic,
                                (scheduler, periodic_interval, action, actionargs))
            action(*actionargs)

        @wraps(func)
        def wrap(
                *args,
                **kwargs
        ):
            """ Wrapper to create our schedule and run it at the appropriate time """
            scheduler = sched.scheduler(time.time, time.sleep)
            periodic(scheduler, interval, func)
            scheduler.run()

        return wrap

    return decorator


@async_job("CPU_Percentage")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['CPU']['PERCENTAGE'].get("INTERVAL", None)).total_seconds())
def CPUPercentage():
    """ Refresh the CPU Percentage """
    # logger.debug("Refresh CPU Percentage")
    stats.CPU.percentage()


@async_job("CPU_Frequency")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['CPU']['FREQUENCY'].get("INTERVAL", None)).total_seconds())
def CPUFrequency():
    """ Refresh the CPU Frequency """
    # logger.debug("Refresh CPU Frequency")
    stats.CPU.frequency()


@async_job("CPU_Load")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['CPU']['LOAD'].get("INTERVAL", None)).total_seconds())
def CPULoad():
    """ Refresh the CPU Load """
    # logger.debug("Refresh CPU Load")
    stats.CPU.load()


@async_job("CPU_Load")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['CPU']['TEMPERATURE'].get("INTERVAL", None)).total_seconds())
def CPUTemperature():
    """ Refresh the CPU Temperature """
    # logger.debug("Refresh CPU Temperature")
    stats.CPU.temperature()
    
    
@async_job("CPU_Load")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['CPU']['LOAD'].get("INTERVAL", None)).total_seconds())
def CPUPower():
    """ Refresh the CPU Power draw """
    # logger.debug("Refresh CPU Power draw")
    stats.CPU.power()


@async_job("GPU_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['GPU'].get("INTERVAL", None)).total_seconds())
def GpuStats():
    """ Refresh the GPU Stats """
    # logger.debug("Refresh GPU Stats")
    stats.Gpu.stats()


@async_job("Memory_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['MEMORY'].get("INTERVAL", None)).total_seconds())
def MemoryStats():
    # logger.debug("Refresh memory stats")
    stats.Memory.stats()


@async_job("Disk_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['DISK'].get("INTERVAL", None)).total_seconds())
def DiskStats():
    # logger.debug("Refresh disk stats")
    stats.Disk.stats()


@async_job("Net_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['NET'].get("INTERVAL", None)).total_seconds())
def NetStats():
    # logger.debug("Refresh net stats")
    stats.Net.stats()


@async_job("Date_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['DATE'].get("INTERVAL", None)).total_seconds())
def DateStats():
    # logger.debug("Refresh date stats")
    stats.Date.stats()


@async_job("Custom_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['CUSTOM'].get("INTERVAL", None)).total_seconds())
def CustomStats():
    # print("Refresh custom stats")
    stats.Custom.stats()


@async_job("Weather_Stats")
@schedule(timedelta(seconds=config.THEME_DATA['STATS']['WEATHER'].get("INTERVAL", None)).total_seconds())
def WeatherStats():
    stats.Weather.stats()


@async_job("Queue_Handler")
@schedule(timedelta(milliseconds=1).total_seconds())
def QueueHandler():
    # Do next action waiting in the queue
    global STOPPING
    if STOPPING:
        # Empty the action queue to allow program to exit cleanly
        while not config.update_queue.empty():
            f, args = config.update_queue.get()
            f(*args)
    else:
        # Execute first action in the queue
        f, args = config.update_queue.get()
        if f:
            f(*args)


def is_queue_empty() -> bool:
    return config.update_queue.empty()
