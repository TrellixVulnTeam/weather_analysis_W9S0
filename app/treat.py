import json
import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import requests

from weather import Data


class Curr:
    curr_time = None
    temp = None
    mid_time = None


def set_curr_time(data_hist):
    if not Curr.curr_time:
        c_time = int(data_hist["current"]["dt"])
        Curr.curr_time = datetime.fromtimestamp(c_time)
        Curr.temp = data_hist["current"]["temp"]
    if not Curr.mid_time:
        Curr.mid_time = Curr.curr_time - timedelta(hours=12)


def forecast(coords):
    api_key = Data.api_key_forecast
    lat, lon = coords[0], coords[1]
    url = "http://api.openweathermap.org/data/2.5/forecast"
    res = requests.get(url, params={"lat": lat,
                                    "lon": lon,
                                    "units": "metric",
                                    "appid": api_key})
    data = json.loads(res.text)
    return get_forecast_arr(data)


def get_forecast_arr(data_f):
    temps = [hour3['main']['temp'] for hour3 in data_f["list"]]
    arr = np.empty((0, 3))
    for i in range(5):
        c_date = Curr.mid_time + timedelta(days=i + 1)
        max_temp = max(temps[:8])
        min_temp = min(temps[:8])
        del temps[:8]
        day = np.array([c_date, min_temp, max_temp])
        arr = np.vstack((arr, day))
    return arr[::-1]


class DayHistWeather:
    def __init__(self, coords, days):
        self.days = days
        self.coords = coords
        self.lat = coords[0]
        self.lon = coords[1]
        self.t_stamp = None
        self.day_temp = []
        self.count = 0
        self.data = None
        self.day_arr = None

    def historical_weather(self):
        api_key = Data.api_key_forecast
        url = "https://api.openweathermap.org/data/2.5/onecall/timemachine"
        res = requests.get(url, params={"lat": self.lat,
                                        "lon": self.lon,
                                        "units": "metric",
                                        "dt": self.t_stamp,
                                        "appid": api_key})
        self.data = json.loads(res.text)

    def get_hist_day(self):
        if len(self.day_temp) >= 24:
            min_temp = min(self.day_temp[:24])
            max_temp = max(self.day_temp[:24])
            mid_date = Curr.mid_time - timedelta(days=self.count - 1)
            self.day_arr = np.array([mid_date, min_temp, max_temp])
            del self.day_temp[:24]

    def treat_data(self):
        set_curr_time(self.data)
        for i in reversed(self.data["hourly"]):
            self.day_temp.append(i["temp"])

    def change_timestamp(self):
        tn = datetime.now(timezone.utc)
        td = timedelta(days=self.count)
        self.t_stamp = str((tn - td).timestamp())[:10]

    def __iter__(self):
        return self

    def __next__(self):
        if self.count < self.days:
            while len(self.day_temp) < 24:
                self.count += 1
                self.change_timestamp()
                self.historical_weather()
                self.treat_data()
            self.get_hist_day()
            return self.day_arr
        else:
            raise StopIteration


def get_hist_array(coords, days):
    arr = np.empty((0, 3))
    for day in DayHistWeather(coords, days):
        arr = np.vstack((arr, day))
    return arr


def weather(coords):
    hist_arr = get_hist_array(coords, 5)
    fore_arr = forecast(coords)
    return np.concatenate((fore_arr, hist_arr))


def save_weather(center: List) -> None:
    city, coords = center[0], center[1]
    path = Data.path_out
    day_10_arr = weather(coords)
    min_temp = day_10_arr[:, 1]
    max_temp = day_10_arr[:, 2]
    date_day = day_10_arr[:, 0]
    fig, ax = plt.subplots()
    ax.plot(date_day, min_temp, "b", label="min day temperature, C")
    ax.plot(date_day, max_temp, "r", label="max day temperature, C")
    plt.scatter(Curr.curr_time, Curr.temp, color='g', s=40,
                marker='o', label=f"current temp. {Curr.temp}, C")
    ax.grid()
    ax.legend()
    plt.xticks(date_day)
    plt.xlabel('Date, 1 day')
    plt.ylabel('Temperature, C')
    plt.title(f'{city[1]}. Day temperature.')
    plt.axvline(x=Curr.curr_time)
    fig.autofmt_xdate()
    new_path = path + city[0] + '\\' + city[1] + '\\'
    if not os.path.isdir(new_path):
        os.makedirs(new_path)
    fig.savefig(new_path + f'weather_{city[1]}.png')


def save_graphics(centres):
    with ProcessPoolExecutor(max_workers=Data.threads) as pool:
        responses = pool.map(save_weather, centres)
    for _ in responses:
        pass