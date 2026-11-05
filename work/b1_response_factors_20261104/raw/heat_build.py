################################################################################
#               The Proof of the Pudding is in the Heating:                    #
#    a Field Experiment on Household Engagement with Heat Pump Flexibility     #
#                                May 2025                    	               #
#            Baptiste Rigaux°, Sam Hamels° and Marten Ovaere°                  #
#         ° Department of Economics, Ghent University (Belgium)                #
#                  Energy Economics, doi: 10.1016/j.eneco.2025.108565          #
################################################################################

# Python replication code to construct the dataset for the monetary valuation of flexibility events.
# Necessary for Fig. 7 (both panels).

# Preamble

import pandas as pd
import datetime

# Defining the directories
path = "C:/Users/" # Change this with your directory

potential_bel3            = pd.read_csv(path + "df_hourly_energy_reduction_bin_1.csv", delimiter = ",", dtype={3: str}, encoding='utf-8')
potential_b36             = pd.read_csv(path + "df_hourly_energy_reduction_bin_2.csv", delimiter = ",", dtype={3: str}, encoding='utf-8')
potential_b69             = pd.read_csv(path + "df_hourly_energy_reduction_bin_3.csv", delimiter = ",", dtype={3: str}, encoding='utf-8')
potential_ab9             = pd.read_csv(path + "df_hourly_energy_reduction_bin_4.csv", delimiter = ",", dtype={3: str}, encoding='utf-8')

dam_prices_data           = pd.read_csv(path + "DAM_prices.csv", delimiter = ",", dtype={3: str}, encoding='utf-8')

weather_data = pd.read_csv(path + "synop_data.csv", delimiter = ",", dtype={3: str}, encoding='utf-8')

# Only work within HS1 and HS2 window (defined as the first/last intervention minus/plus one week)

hs1_start = pd.to_datetime("21/11/2022 00:00:00") - pd.Timedelta(weeks=1)
hs1_end = pd.to_datetime("15/04/2023 00:00:00") + pd.Timedelta(weeks=1)

hs2_start = pd.to_datetime("30/10/2023 00:00:00") - pd.Timedelta(weeks=1)
hs2_end = pd.to_datetime("24/03/2024 00:00:00") + pd.Timedelta(weeks=1)

# Preparation of the DAM dataset

dam_prices_data['time'] = pd.to_datetime(dam_prices_data['time'], format='%d%b%Y %H:%M:%S', dayfirst=True)

dam_prices_data_filtered = dam_prices_data[(dam_prices_data['time'] >= hs1_start) & (dam_prices_data['time'] <= hs1_end) |
                 (dam_prices_data['time'] >= hs2_start) & (dam_prices_data['time'] <= hs2_end)]

# Preparation of the weather dataset 

weather_data_filtered = weather_data[weather_data['code'] == 6434] # Melle station only 
weather_data_filtered = weather_data_filtered[(weather_data_filtered['wind_speed_unit'] == 0) | (weather_data_filtered['wind_speed_unit'] == 1)]

# Select the specified columns
weather_data_filtered = weather_data_filtered[['timestamp', 'temp','wind_speed','wind_speed_unit','humidity_relative','cloudiness', 'sun_duration_24hours']]

# Ensure the column name is correct, update 'time' if needed
weather_data_filtered = weather_data_filtered.sort_values('timestamp')  # Replace 'time' with actual column name if different

# Ensure the 'time' column is in datetime format
weather_data_filtered['timestamp'] = pd.to_datetime(weather_data_filtered['timestamp'])

# Extract the day for grouping
weather_data_filtered['day'] = weather_data_filtered['timestamp'].dt.date

# Forward fill the 'sun_radiation' value
weather_data_filtered['sun_duration_24hours'] = weather_data_filtered.groupby('day')['sun_duration_24hours'].ffill()

# Drop the 'day' column
weather_data_filtered.drop(columns=['day'], inplace=True)

weather_data_filtered.rename(columns={'timestamp': 'time'}, inplace=True)

weather_data_Melle_prepared = weather_data_filtered[
    (weather_data_filtered['time'] >= hs1_start) & (weather_data_filtered['time'] <= hs1_end) |
    (weather_data_filtered['time'] >= hs2_start) & (weather_data_filtered['time'] <= hs2_end)
]

average_DAM_price = dam_prices_data['DAM_price'].mean()
print(average_DAM_price)

dict_potential_avg_bel3 = {int(row['hour_into_int']): float(row['avg_hourly_energy_reduction']) for _, row in potential_bel3.iterrows()}

dict_potential_avg_b36 = {int(row['hour_into_int']): float(row['avg_hourly_energy_reduction']) for _, row in potential_b36.iterrows()}

dict_potential_avg_b69 = {int(row['hour_into_int']): float(row['avg_hourly_energy_reduction']) for _, row in potential_b69.iterrows()}

dict_potential_avg_ab9 = {int(row['hour_into_int']): float(row['avg_hourly_energy_reduction']) for _, row in potential_ab9.iterrows()}

# Incrementation to correct for the shift induced, really important in the values it gives. 
# At hour_into_int = x, the potential is given from hour x-1 to x. So we stop phase 1 at x = 18, phase 2 at x = 36.

incremented_dict_bel3 = {key + 1: value for key, value in dict_potential_avg_bel3.items()}
incremented_dict_b36 = {key + 1: value for key, value in dict_potential_avg_b36.items()}
incremented_dict_b69 = {key + 1: value for key, value in dict_potential_avg_b69.items()}
incremented_dict_ab9 = {key + 1: value for key, value in dict_potential_avg_ab9.items()}

new_df = pd.merge(dam_prices_data_filtered, weather_data_Melle_prepared, on= 'time', how= 'outer')

def classify_category(avg_t_out_on_18h):
    eligible_to_bel3 = 0
    eligible_to_b36 = 0
    eligible_to_b69 = 0
    eligible_to_ab9 = 0

    # Assign categories based on temperature
    if avg_t_out_on_18h <= 3:
        eligible_to_bel3 = 1
    if 3 <= avg_t_out_on_18h < 6:
        eligible_to_b36 = 1
    if 6 <= avg_t_out_on_18h < 9:
        eligible_to_b69 = 1
    if avg_t_out_on_18h >= 9:
        eligible_to_ab9 = 1

    # Return the final choice based on the assigned eligibility
    if eligible_to_bel3 == 1:
        return ["bel3",incremented_dict_bel3]
    elif eligible_to_b36 == 1:
        return ["b36",incremented_dict_b36]
    elif eligible_to_b69 == 1:
        return ["b69",incremented_dict_b69]
    elif eligible_to_ab9 == 1:
        return ["ab9",incremented_dict_ab9]
    
for i in range(len(new_df.index) - 36):
    avg_money_saved = 0 

    money_saved_mean_DAM_price = 0

    # Calculate the average temperatures for the intervals required by the function  
    avg_t_out_on_18h = new_df.iloc[i:i + 18]['temp'].mean()
    avg_t_out_on_36h = new_df.iloc[i:i + 36]['temp'].mean()
    avg_dam_on_18h = new_df.iloc[i:i + 18]['DAM_price'].mean()
    avg_dam_on_36h = new_df.iloc[i:i + 36]['DAM_price'].mean()
    
    # Call the function to determine the category
    final_choice = classify_category(avg_t_out_on_18h)
    new_df.at[i, 'temp_heterogeneity_category'] = final_choice[0]        
    potential_to_use = final_choice[1]

    # Calculation of the savings 
    for j in range(i + 1, i + 37):
        
        hour_into_int = j-i

        price_for_this_hour = new_df.loc[j, 'DAM_price']        
        
        avg_money_saved += price_for_this_hour * potential_to_use[hour_into_int]
        money_saved_mean_DAM_price += average_DAM_price * potential_to_use[hour_into_int]
        
        if hour_into_int == 18:
            avg_money_phase1 = avg_money_saved
            money_saved_mean_DAM_phase1 = money_saved_mean_DAM_price
            
            new_df.at[i, 'phase1_avg_money'] = avg_money_phase1
            new_df.at[i, 'phase1_mean'] = money_saved_mean_DAM_phase1
            

    new_df.at[i, 'phase2_avg_money'] = avg_money_saved
    new_df.at[i, 'phase2_mean'] = money_saved_mean_DAM_price    
    
    new_df.at[i, 'avg_t_out_on_18h'] = avg_t_out_on_18h    
    new_df.at[i, 'avg_t_out_on_36h'] = avg_t_out_on_36h    
    new_df.at[i, 'avg_dam_on_18h'] = avg_dam_on_18h    
    new_df.at[i, 'avg_dam_on_36h'] = avg_dam_on_36h    
    
new_df.to_csv("money_shifted_heterogeneous.csv", index = False)
