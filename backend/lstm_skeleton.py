from station_data import station_data
from api_fetch import get_weather_data, get_pm25_data, get_final_df
'''from LSTMfiles import LSTMFunction'''

for name, data in station_data.items():
    start_date = '20250726'
    end_date = '20250730'
    latitude, longitude, county, site = data[0:4]
    nominal = data[-1]

    weather = get_weather_data(start_date, end_date, latitude, longitude)
    pm25 = get_pm25_data(start_date, end_date, county, site)
    df = get_final_df(weather, pm25)
    lstm_data = df.to_numpy()

    '''
    vis_data = LSTMFunction(lstm_data, nominal)
    
    LSTMFunction will load an LSTMRegressor with a MODEL_PATH and SCALER_PATH
    and output a DataFrame of predicted PV generation scaled according to a
    nominal capacity.
    '''