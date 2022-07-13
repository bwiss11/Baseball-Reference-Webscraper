#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 27 17:34:58 2022

@author: bwiss

New in v1.2: Postponement checker was added in. Now when the schedule is scraped, there is a background
check occurring that uses ESPN and notifies the user if there were games postponed to the following day.
BBRef is sometimes slow to update the schedule with postponements so this makes sure the user is aware
of any postponements that BBRef may be missing.

New in v1.1: The way games are ordered in the scores dataframes was slightly altered. BBRef hasn't
been as good about getting correct game start times in, which is what the order of the games
is based on. They still list Game 1 as starting before Game 2 but oftentimes with the same hour
(i.e. Game 1 starting at 3:10 pm and Game 2 at 3:15 pm). The ordering had previously only used
the hour for the start time but when the hour was listed as the same for both Game 1 and Game 2,
Game 2 was listed before Game 1 in the scores dataframes which was throwing off the Win/Loss
checker for doubleheaders in the Google Sheet. The ordering is now based on both the start
time's hour and minutes, which has solved the issue.
"""

import PySimpleGUI as sg
import datetime
from datetime import date
import calendar
from bs4 import BeautifulSoup
import requests
import pandas as pd
from pandas import DataFrame
import datetime
from datetime import date
import calendar
import webbrowser
import re
import sys

##### PYSIMPLEGUI SECTION - Creates the UI to interface with the backend code #####
sg.theme('DarkBlack')
# Creates the column for the schedule scraping options
col1 = [
    [sg.Frame('', [
        [sg.Text('Schedule', justification='center', size=(18, 1), font=('Arial', '16'))],
    ])],
    [sg.Frame('', [
        [sg.Button("Today's Schedule")],
        [sg.Button("Tomorrow's Schedule")],
        [sg.Frame('Custom Date Schedule', [
            [sg.Text('Month Number:', size=(12, 1)), sg.InputText(size=10, key='Month Schedule')],
            [sg.Text('Day Number:', size=(12, 1)), sg.InputText(size=10, key='Day Schedule')],
            [sg.Text('Year Number:', size=(12, 1)), sg.InputText(size=10, default_text='2022', key='Year Schedule')],
            [sg.Button("Submit Schedule Request")],
        ])],
    ])]
]
# Creates the column for the score scraping options
col2 = [
    [sg.Frame('', [
        [sg.Text('Scores', justification='center', size=(18, 1), font=('Arial', '16'))]
    ])],
    [sg.Frame('', [
        [sg.Button("Yesterday's Scores")],
        [sg.Button("Today's Scores")],
        [sg.Frame('Custom Date Scores', [
            [sg.Text('Month Number:', size=(12, 1)), sg.InputText(size=10, key='Month Scores')],
            [sg.Text('Day Number:', size=(12, 1)), sg.InputText(size=10, key='Day Scores')],
            [sg.Text('Year Number:', size=(12, 1)), sg.InputText(size=10, default_text='2022', key='Year Scores')],
            [sg.Button("Submit Scores Request")]
        ])],
    ])]
]
# Sets the layout using the schedule and scores columns created above
layout = [[
    [sg.Frame('', [
        [sg.Text('Baseball Reference Webscraper', text_color='white', justification='center', size=(34, 1),
                 font=('Arial', '24', 'bold'))]
    ])],
    sg.Column(col1, pad=(30, 10), element_justification='center', background_color='grey18'),
    sg.Column(col2, pad=(30, 10), element_justification='center', background_color='grey18'),
]]
# Creates the window containing the layout created above
window = sg.Window("BBRef Schedule and Scores Scraper", layout, margins=(50, 20), background_color='grey18')
# Creates an event loop that breaks the loop after a button is pressed that allows the window to be closed
while True:
    event, values = window.read()
    # End program if user closes window or
    # presses the OK button
    if event == "Submit Schedule Request" or event == "Today's Schedule" or event == "Tomorrow's Schedule" or event == "Yesterday's Scores" or event == "Today's Scores" or event == "Custom Date Scores" or event == "Submit Scores Request" or event == sg.WIN_CLOSED:
        break
window.close()

##### BACKEND CODE SECTION - code for the actual webscraping of schedule and scores #####
# Dictionary of each team's full name and their 3-letter abbreviated name to be used later.
abbr_dict = {'Boston Red Sox': 'BOS', 'Baltimore Orioles': 'BAL', 'Tampa Bay Rays': 'TBR', 'Toronto Blue Jays': 'TOR',
             'New York Yankees': 'NYY', 'Chicago White Sox': 'CHW', 'Kansas City Royals': 'KCR',
             'Detroit Tigers': 'DET', 'Minnesota Twins': 'MIN', 'Cleveland Guardians': 'CLE',
             'Oakland Athletics': 'OAK', 'Houston Astros': 'HOU', 'Seattle Mariners': 'SEA',
             'Los Angeles Angels': 'LAA', 'Texas Rangers': 'TEX', 'Atlanta Braves': 'ATL', 'Miami Marlins': 'MIA',
             'Philadelphia Phillies': 'PHI', 'New York Mets': 'NYM', 'Washington Nationals': 'WAS',
             'Chicago Cubs': 'CHC', 'St. Louis Cardinals': 'STL', 'Cincinnati Reds': 'CIN', 'Milwaukee Brewers': 'MIL',
             'Pittsburgh Pirates': 'PIT', 'Los Angeles Dodgers': 'LAD', 'San Diego Padres': 'SDP',
             'San Francisco Giants': 'SFG', 'Colorado Rockies': 'COL', 'Arizona D\'Backs': 'ARI',
             'Arizona Diamondbacks': 'ARI'}


# Defining of several functions to be used throughout the scraping sections
def parse(list):
    '''Converts a list of beautifulsoup strings to a list of Python strings'''
    return [str(x.string) for x in list]


def dates_without_days_compiler():
    '''Creates a new list and then breaks the previous list up into the dates without the day of the week in front'''
    dates_without_days = []
    for date in parsed_dates:
        if date == 'Today\'s Games':
            dates_without_days.append(date)
        else:
            comma = date.find(',')
            dates_without_days.append(date[(comma + 2):])
    # Re-adds the first table's title if its title is "Today's Games" since it's in a different format from
    # the rest of the dates. Sometimes BBRef has it as "Today's Games", sometimes as just the date
    if dates_without_days[0] == 'oday\'s Games':
        dates_without_days[0] = 'Today\'s Games'
    return dates_without_days


def teams_df_creator():
    '''Creates the teams_df which contains the home and away teams for each game'''
    # Uses parsing function and puts the Python strings into a list, then a flattened list,
    # then converts full names to abbreviations
    # Then cuts out the "Preview" column that BBRef provides for games.
    # Then puts teams into a DataFrame.
    # Then reshapes the DataFrame, putting the home teams into one column and away teams into another
    # Then renames the columns.
    list_of_parsed_teams = [parse(team) for team in teams_list]
    flattened_list_of_parsed_teams = [team for sublist in list_of_parsed_teams for team in sublist]
    list_abbr_teams = [abbr_dict.get(n, n) for n in flattened_list_of_parsed_teams]
    list_abbr_teams = [team for team in list_abbr_teams if team != 'Preview']
    teams_df = DataFrame(list_abbr_teams)
    teams_df = pd.DataFrame(teams_df.values.reshape(-1, 2))
    teams_df.rename(columns={0: 'Away', 1: 'Home'}, inplace=True)
    return teams_df


def time_df_creator():
    '''Creates the time_df which contains the start time for each game'''
    # All the game start times in each 'table' are tagged with 'strong'. This puts all those into a list.
    times_list = table.find_all('strong')
    # Parses the times_list and puts them into Python strings instead of BS4 strings.
    # Then puts that list into a DataFrame and renames the column.
    list_of_parsed_times = [parse(row) for row in times_list]
    time_df = DataFrame(list_of_parsed_times)
    time_df.rename(columns={0: 'Time'}, inplace=True)
    return time_df


def table_date():
    # Finds the date that you're pulling the games from and stores the value to be put into the full
    # DataFrame later on.
    date_of_table_list = table.find_all('h3')
    date_of_table = [parse(row) for row in date_of_table_list]
    date_of_table_flattened = date_of_table[0]
    date_of_table_str = date_of_table_flattened[0]
    if date_of_table_str == "Today's Games":
        return date_of_table_str
    date_of_table_str = date_of_table_str[date_of_table_str.find(',') + 2:]
    return date_of_table_str


def postponement_checker(day, month):
    '''Cunction that checks with ESPN to make sure BBRef isn't missing any game's from the day before that got postponed to the date of interest'''
    # Helper dictionaries for team names and days per month
    ESPN_abbr_dict = {'Boston': 'BOS', 'Baltimore': 'BAL', 'Tampa Bay': 'TBR', 'Toronto': 'TOR', 'New York': 'NY',
                      'Chicago': 'CH', 'Kansas City': 'KCR', 'Detroit': 'DET', 'Minnesota': 'MIN', 'Cleveland': 'CLE',
                      'Oakland': 'OAK', 'Houston': 'HOU', 'Seattle': 'SEA', 'Los Angeles': 'LA', 'Texas': 'TEX',
                      'Atlanta': 'ATL', 'Miami': 'MIA', 'Philadelphia': 'PHI', 'New York': 'NY', 'Washington': 'WAS',
                      'Chicago': 'CH', 'St. Louis': 'STL', 'Cincinnati': 'CIN', 'Milwaukee': 'MIL', 'Pittsburgh': 'PIT',
                      'Los Angeles': 'LA', 'San Diego': 'SDP', 'San Francisco': 'SFG', 'Colorado': 'COL',
                      'Arizona': 'ARI'}
    ESPN_abbr_mascots = ['Red Sox', 'Orioles', 'Rays', 'Blue Jays', 'Yankees', 'White Sox', 'Royals', 'Tigers', 'Twins',
                         'Guardians', 'Angels', 'Astros', 'Mariners', 'Athletics', 'Rangers', 'Mets', 'Phillies',
                         'Nationals', 'Braves', 'Marlins', 'Brewers', 'Cardinals', 'Pirates', 'Cubs', 'Reds', 'Dodgers',
                         'Giants', 'Padres', 'Rockies', 'Diamondbacks']
    days_per_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    # Sets the date that will be used in the link to the ESPN page for the next day
    month_object = datetime.datetime.strptime(str(month), "%m")
    month_name = month_object.strftime("%B")
    next_day = day + 1
    if next_day > days_per_month[month]:
        next_day = 1
    if int(month) < 10:
        if int(day) < 10:
            date = "20220" + str(month) + "0" + str(day)
            next_date = "20220" + str(month) + "0" + str(next_day)
        elif int(day) == days_per_month[month]:
            date = "20220" + str(month) + str(day)
            next_date = "20220" + str(month + 1) + "0" + str(next_day)
        else:
            date = "20220" + str(month) + str(day)
            next_date = "20220" + str(month) + str(next_day)
    else:
        if int(day) < 10:
            date = "2022" + str(month) + "0" + str(day)
            next_date = "2022" + str(month1) + "0" + str(next_day)
        else:
            date = "2022" + str(month) + str(day)
            next_date = "2022" + str(month1) + str(next_day)
    if next_day == 1:
        month_object = datetime.datetime.strptime(str(month + 1), "%m")
        month_name = month_object.strftime("%B")
    # Goes to ESPN's schedule for the given date and creates a BeautifulSoup object.
    response = requests.get('https://www.espn.com/mlb/scoreboard/_/date/' + date)
    soup = BeautifulSoup(response.text, features="html.parser")
    # Finds all tables, then retrieves the table of the day's games (first table), then finds the table's rows
    tables = soup.find_all('body')
    table = tables[0]
    rows = table.find_all('section', {'class': 'Scoreboard bg-clr-white flex flex-auto justify-between'})
    # Goes through each of the games and finds any that are supposed to be made up the next day, adds them to a list
    postponed_list = []
    for row in rows:
        div_tags = row.find_all('div')
        parsed_table = parse(div_tags)
        teams_helper = []
        for item in parse(div_tags):
            if item in ESPN_abbr_mascots:
                teams_helper.append(item)
        teams = []
        [teams.append(team) for team in teams_helper if team not in teams]
        if any(month_name + ' ' + str(next_day) in s for s in parse(div_tags)):
            postponed_list.append(f'{teams[0]}-{teams[1]}')
            webbrowser.open('https://www.espn.com/mlb/scoreboard/_/date/' + next_date)
    return postponed_list


def postponed_popup(passed_list, passed_day):
    '''Notifies the user via popup window if there are postponed games rescheduled for the next day'''
    if len(passed_list) == 1:
        sg.Popup('Postponed Games Rescheduled for ' + passed_day +':', passed_list[0], title='Postponed Games',
                 font=('Arial', '14'))
    if len(passed_list) == 2:
        sg.Popup('Postponed Games Rescheduled for the Next Day:', passed_list[0], passed_list[1],
                 title='Postponed Games', font=('Arial', '14'))
    if len(passed_list) == 3:
        sg.Popup('Postponed Games Rescheduled for the Next Day:', passed_list[0], passed_list[1], passed_list[2],
                 title='Postponed Games', font=('Arial', '14'))
    if len(passed_list) == 4:
        sg.Popup('Postponed Games Rescheduled for the Next Day:', passed_list[0], passed_list[1], passed_list[2],
                 passed_list[3], title='Postponed Gammes', font=('Arial', '14'))
    if len(passed_list) == 5:
        sg.Popup('Postponed Games Rescheduled for the Next Day:', passed_list[0], passed_list[1], passed_list[2],
                 passed_list[3], passed_list[4], title='Postponed Games', font=('Arial', '14'))


### SCHEDULE SCRAPING SECTION ###
# Section is initiated if any of the schedule buttons are clicked, initiates the framework for all three
# types of schedule scraping (yesterday, today, custom date)
if event == "Today's Schedule" or event == "Tomorrow's Schedule" or event == "Submit Schedule Request":
    # Requests the BBRef schedule page and creates a BeautifulSoup object to parse through
    response = requests.get('https://www.baseball-reference.com/leagues/MLB-schedule.shtml')
    soup = BeautifulSoup(response.text, features="html.parser")
    # 'Tables' of day's games are broken up into 'div' class in this case, to be used later
    tables = soup.find_all('div')
    # Finds all <li> html tags with the end intention of finding the index of the last non-date
    # "table" (<div> tags)
    li = soup.find_all('li')
    parsed_li = parse(li)
    # The last non-date table has the <li> tag that says "all times Eastern"
    # This finds its position among the parsed li tags list.
    all_times_eastern_position = parsed_li.index('all times Eastern')
    # Uses the index of the "all times Eastern" <li> tag to find that tag, and find its parent tag
    # to get the <ul> tag its nested in, then finds its parent tag again to get the <div> tag of
    # interest
    all_times_eastern_div = li[all_times_eastern_position].parent.parent
    # Matches the div tag of interest (last non-date "table" /<div>) to its position among all the
    # div tags
    all_times_eastern_div_position = tables.index(all_times_eastern_div)
    # Uses the last non-date "table" position and adds two to get the first (single) date table
    # position. The "first" date table appears to be one long table containing all the dates, and
    # then the tables after that break into single dates, which is what is watnted
    first_date_table_position = all_times_eastern_div_position + 2
    # Narrows it down to only the tables of dates/games and onward using the position found above
    date_tables = tables[first_date_table_position:]
    # Establishes today's date for use later on
    today_date = datetime.date.today()
    # Establishes tomorrow's date for use later on.
    tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
    tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)

# Section for scraping today's schedule, initialized by clicking the "Today's Schedule" button
if event == "Today's Schedule":
    # Gets today's date and then formats it in the same way BBRef formats dates
    date = today_date.strftime('%-m.%-d.%y')
    today_date_formatted = today_date.strftime('%B %-d, %Y')
    # First finds all the dates on the page
    # Then parses the dates and puts them in a list of Python strings
    dates = soup.find_all('h3')
    parsed_dates = parse(dates)
    dates_without_days = dates_without_days_compiler()
    # First tries to find a table titled with today's date and if no table is found with today's date,
    # the games for today are likely in a table titled "Today's Games" which is handled in the else
    # statement below
    if today_date_formatted in dates_without_days:
        # Gets position of table that matches today's date
        table_position = dates_without_days.index(today_date_formatted)
        # Defines the table of interest based on the position of the matched date
        table = date_tables[table_position]
        # All the teams in each "table" are tagged with 'a'
        # This puts those all in a list
        teams_list = table.find_all('a')
        # Creates teams and times DataFrames using previously defined functions
        teams_df = teams_df_creator()
        time_df = time_df_creator()
        # Finds the date of the BBRef 'table' you're pulling games from
        date_of_table_str = table_date()
        # Establishes the month and day number for later use
        month_number = today_date.strftime('%-m')
        day = today_date.strftime('%-d')
        month_full = today_date.strftime('%-m')
        month = today_date.strftime('%-m')
        # Handles the case where today's date isn't found as the header of any tables in the if statement above
    # This will occur when today's games are in a table titled "Today's Games" instead of the actual date
    # Beyond that, goes through virtually the exact same process as the if statement above
    else:
        # Gets position of table that matches today's date
        table_position = dates_without_days.index('Today\'s Games')
        # Defines the table of interest based on the position of the matched date
        table = date_tables[table_position]
        # All the teams in each "table" are tagged with 'a'
        # This puts those all in a list
        teams_list = table.find_all('a')
        # Creates teams and times DataFrames using previously defined functions
        teams_df = teams_df_creator()
        time_df = time_df_creator()
        # Finds the date of the BBRef 'table' you're pulling games from
        date_of_table_str = table_date()
        # Splits the date of the table that we pulled games from into month and day
        # Converts month from its full name to its number
        # Adds the date to the DataFrame
        # Will stamp the DataFrame with the date the games were actually pulled from, rather than just the date the user intended as in v1.2
        # This ensures you are not pulling games in from a table of a different date due to
        # some sort of error and are not aware of it
        if date_of_table_str != "Today's Games":
            split_month = date_of_table_str.split(' ')
            split_month = split_month[1:]
            month_full = split_month[0]
            month_object = datetime.datetime.strptime(month_full, "%B")
            month_number = month_object.month
            split_day = split_month[1].split(',')
            day = split_day[0]
        else:
            month_number = today_date.strftime('%-m')
            day = today_date.strftime('%-d')
    # Combines the teams and time DataFrames, adds the date, and resets the index, then copies it to clipboard
    # Notifies the user via print what the title of the table is on BBRef that the schedule was taken from (either
    # 'Today's Games' or the day's date) to ensure right date was pulled
    # Stamps the DataFrame with the date from the table the games were pulled from via the method shown above
    full_df = pd.concat([teams_df, time_df], axis=1)
    full_df.set_index('Away', inplace=True)
    date = today_date.strftime('%-m.%-d.%y')
    if date_of_table_str != "Today's Games":
        full_df['Date'] = str(month_number) + '.' + str(day) + '.22'
    else:
        full_df['Date'] = date
    # Prints full schedule for the given day
    # Notifies the user via print what the title of the table is on BBRef that the schedule
    # was taken from to ensure the right date was pulled
    # Copies the full schedule to clipboard to be pasted
    print('\n')
    print(full_df)
    print('\nTitle of table on Baseball Reference: ' + date_of_table_str + '\n')
    full_df.to_clipboard()
    # Runs the postponement checker and notifies the user if there are any postponed games rescheduled for the next day
    yesterday_date = datetime.date.today() - datetime.timedelta(days=1)
    month = int(yesterday_date.strftime('%-m'))
    day = int(yesterday_date.strftime('%-d'))
    postponed_list = postponement_checker(day, month)
    postponed_popup(postponed_list, "Today")



# Section for scraping tomorrow's schedule, initialized by clicking the "Tomorrow's Schedule" button
elif event == "Tomorrow's Schedule":
    # Gets tomorrow's date and then formats it in the same way BBRef formats dates
    date = tomorrow_date.strftime('%-m.%-d.%y')
    # First finds all the dates on the page
    # Then parses the dates and puts them in a list of Python strings
    dates = soup.find_all('h3')
    parsed_dates = parse(dates)
    dates_without_days = dates_without_days_compiler()
    # Gets tomorrow's date and puts it into the same format as dates_without_days table
    # NOTE: '%#d' is used on Windows to cut leading zero, not needed on Mac
    tomorrow_date_formatted = tomorrow_date.strftime('%B %-d, %Y')
    # Finds which number table tomorrow's games are in (its position)
    table_position = dates_without_days.index(tomorrow_date_formatted)
    table = date_tables[table_position]
    # All the teams in each "table" are tagged with 'a'. This puts those all in a list
    teams_list = table.find_all('a')
    # Creates teams and times DataFrames using previously defined functions
    teams_df = teams_df_creator()
    time_df = time_df_creator()
    # Finds the date of the BBRef 'table' you're pulling games from
    date_of_table_str = table_date()
    # Splits the date of the table that we pulled games from into month and day
    # Converts month from its full name to its number
    # Adds the date to the DataFrame
    # Will stamp the DataFrame with the date the games were actually pulled from, rather than just the date the user intended as in v1.2
    # This ensures you are not pulling games in from a table of a different date due to
    # some sort of error and are not aware of it
    full_df = pd.concat([teams_df, time_df], axis=1)
    full_df.set_index('Away', inplace=True)
    date = tomorrow_date.strftime('%-m.%-d.%y')
    if date_of_table_str != "Today's Games":
        split_month = date_of_table_str.split(' ')
        month_full = split_month[0]
        month_object = datetime.datetime.strptime(month_full, "%B")
        month_number = month_object.month
        split_day = split_month[1].split(',')
        day = split_day[0]
        full_df['Date'] = str(month_number) + '.' + str(day) + '.22'
    else:
        month_number = today_date.strftime('%-m')
        # Gets today's date and then formats it in the same way BBRef formats dates.
        day = today_date.strftime('%-d')
    # Prints full schedule for the given day
    # Notifies the user via print what the title of the table is on BBRef that the schedule was taken from to ensure
    # right date was pulled
    # Copies the full schedule to clipboard
    print('\n')
    print(full_df)
    print('\nTitle of table on Baseball Reference: ' + date_of_table_str + '\n')
    full_df.to_clipboard()
    # Runs the postponement checker and notifies the user if there are any postponed games rescheduled for the next day
    today_date = datetime.date.today()
    month = int(today_date.strftime('%-m'))
    day = int(today_date.strftime('%-d'))
    postponed_list = postponement_checker(day, month)
    postponed_popup(postponed_list, "Tomorrow")



# Section for scraping the schedule from a custom date, initialized by clicking the "Submit Schedule Request" button
elif event == "Submit Schedule Request":
    # Gets the month, day, and year from the user-inputted data and converts them to the necessary format
    month = values['Month Schedule']
    month_full = calendar.month_name[int(values['Month Schedule'])]
    day = values['Day Schedule']
    year = values['Year Schedule']
    full_date = month_full + ' ' + day + ', ' + year
    # First finds all the dates on the page
    # Then parses the dates and puts them in a list of Python strings
    dates = soup.find_all('h3')
    parsed_dates = parse(dates)
    dates_without_days = dates_without_days_compiler()
    # Tries to find the user-input date (should always work unless the date is titled "Today's Games" on
    # BBRef, in which case the 'except' statement below will handle that).
    try:
        print()
        ### Finds which number table the specified games are in (its position) among all the dates
        table_position = dates_without_days.index(full_date)
        # Creates a variable for just the table of the specific date that was entered
        table = date_tables[table_position]
        # All the teams in each "table" are tagged with 'a'
        # This puts those all in a list
        teams_list = table.find_all('a')
        # Creates teams and times DataFrames using previously defined functions
        teams_df = teams_df_creator()
        time_df = time_df_creator()
        # Finds the date of the BBRef 'table' you're pulling games from
        date_of_table_str = table_date()
    # Handles the case where today's date isn't found as the header of any tables in the try statement
    # above. This will occur when today's games are in a table titled "Today's Games" instead of the actual
    # date.
    # Beyond that, goes through virtually the exact same process as the try statement above.
    except ValueError:
        # Makes sure it only looks for today's games if the user-entered date is today's date.
        if str(month) == today_date.strftime('%-m') and day == today_date.strftime('%-d'):
            table_position = dates_without_days.index('Today\'s Games')
            table = date_tables[table_position]
            # All the teams in each "table" are tagged with 'a'
            # This puts those all in a list
            teams_list = table.find_all('a')
            # Creates teams and times DataFrames using previously defined functions
            teams_df = teams_df_creator()
            time_df = time_df_creator()
            # Finds the date of the BBRef 'table' you're pulling games from
            date_of_table_str = table_date()
        else:
            print('ERROR')
            # Combines the teams and time DataFrames, adds the date, and resets the index
    full_df = pd.concat([teams_df, time_df], axis=1)
    full_df.set_index('Away', inplace=True)
    # Splits the date of the table that we pulled games from into month and day
    # Converts month from its full name to its number
    # Adds the date to the DataFrame
    # Will stamp the DataFrame with the date the games were actually pulled from, rather than just the date the user intended as in v1.2
    # This ensures you are not pulling games in from a table of a different date due to
    # some sort of error and are not aware of it
    date = today_date.strftime('%-m.%-d.%y')
    if date_of_table_str != "Today's Games":
        split_month = date_of_table_str.split(' ')
        month_full = split_month[0]
        month_object = datetime.datetime.strptime(month_full, "%B")
        month_number = month_object.month
        split_day = split_month[1].split(',')
        day = split_day[0]
        full_df['Date'] = str(month_number) + '.' + str(day) + '.22'
    else:
        full_df['Date'] = date
    # Prints full schedule for the given day.
    # Notifies the user via print what the title of the table is on BBRef that the schedule was taken from to ensure
    # right date was pulled.
    # Copies the full schedule to clipboard.
    print('\n')
    print(full_df)
    print('\nTitle of table on Baseball Reference: ' + date_of_table_str + '\n')
    full_df.to_clipboard()
    # Runs the postponement checker and notifies the user if there are any postponed games rescheduled for the next day
    days_per_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    month = int(values['Month Schedule'])
    day = int(values['Day Schedule']) - 1
    if day == 0:
        month -= 1
        day = days_per_month[month]
    postponed_list = postponement_checker(day, month)
    postponed_popup(postponed_list, "This Day")


### SCORES SECTION
# Definition of the function that creates the scores DataFrame
def scores_compiler(month, day, year):
    '''Function that scrapes through BBRef's site to find the scores for a user-selected/entered date'''
    # Creates a blank local start times list to be appended to later on
    local_start_times = []
    # Retrieves the page for all scores of the date passed as arguments to the function
    response = requests.get(
        'https://www.baseball-reference.com/boxes/?year=' + year + '&month=' + month + '&day=' + day)
    # Creates a BeautifulSoup object of the webpage
    soup = BeautifulSoup(response.text, features="html.parser")
    # Creates a blank dDataFrame where each game's box score will eventually be written in at the end of
    # the for loop below
    all_games_df = pd.DataFrame()
    # Retrieves a list of all the individual games' code to be cycled through in the 'for loop' below
    games = soup.find_all('div', {'class': 'game_summary nohover'})
    # For loop to cycle through each game in the 'games' list above and find the inning-by-inning box score.
    # Inning-by-inning box score is then appended to the blank 'all_games_df' created above
    for game in games:
        # Finds the link to the box score for the given game in the list 'games'
        link = game.find_all('a', href=re.compile('boxes'))
        # Parses the BS4 link (which is really just the end of the actual box score link) into a Python
        # string and then adds it to the generic baseball-reference address to get the full link
        parsed_link = parse(link)
        for individual_link in link:
            link_ending = (individual_link['href'])
        full_link = 'https://www.baseball-reference.com/' + link_ending
        # Retrieves the page for the box score of the given game in the list 'games' and creates a
        # BeautifulSoup object
        game_response = requests.get(full_link)
        game_soup = BeautifulSoup(game_response.text, features="html.parser")
        ### Away Team Section
        # Retrieves the away team and finds the abbreviation.
        tr = game_soup.find_all('tr')
        a_tags = tr[1].find_all('a')
        parsed_a_tags = parse(a_tags)
        away_team = parsed_a_tags[-1]
        away_team = abbr_dict.get(away_team)
        # Retrieves the inning-by-inning scores for the away team, parses them, and cleans them up
        # (removes occurrences of 'None')
        away_td = tr[1].find_all('td', {'class': 'center'})
        parsed_away_td = parse(away_td)
        parsed_away_td = [td for td in parsed_away_td if td != 'None']
        # Turns all the inning-by-inning scores into integers unless there is
        # an 'X', which indicates team did not bat in that half inning
        parsed_away_td_ints = []
        for item in parsed_away_td:
            if item != 'X':
                parsed_away_td_ints.append(int(item))
            else:
                parsed_away_td_ints.append(item)
        # Creates a dataframe of the away team's inning-by-inning scores, and renames the columns
        away_df = DataFrame(parsed_away_td_ints)
        away_df = pd.DataFrame(away_df.values.reshape(1, int(len(parsed_away_td))), index=[away_team])
        away_df.rename(
            columns={0: '1', 1: '2', 2: '3', 3: '4', 4: '5', 5: '6', 6: '7', 7: '8', 8: '9', 9: '10', 10: '11',
                     11: '12', 12: '13', 13: '14', 14: '15', 15: '16', 16: '17', 17: '18', 18: '19', 19: '20', 20: '21',
                     21: '22', 22: '23', 23: '24', 24: '25', 25: '26', away_df.columns[-3]: 'R',
                     away_df.columns[-2]: 'H', away_df.columns[-1]: 'E'}, inplace=True)
        ### Home Team Section
        # Retrieves the home team and finds the abbreviation
        tr = game_soup.find_all('tr')
        a_tags = tr[2].find_all('a')
        parsed_a_tags = parse(a_tags)
        home_team = parsed_a_tags[-1]
        home_team = abbr_dict.get(home_team)
        # Retrieves the inning-by-inning scores for the away team, parses them, and cleans them up
        # (removes occurrences of 'None')
        home_td = tr[2].find_all('td', {'class': 'center'})
        parsed_home_td = parse(home_td)
        parsed_home_td = [td for td in parsed_home_td if td != 'None']
        # Turns all the inning-by-inning scores into integers unless there is
        # an 'X', which indicates team did not bat in that half inning
        parsed_home_td_ints = []
        for item in parsed_home_td:
            if item != 'X':
                parsed_home_td_ints.append(int(item))
            else:
                parsed_home_td_ints.append(item)
        # Creates a DataFrame of the home team's inning-by-inning scores, and renames the columns
        home_df = DataFrame(parsed_home_td_ints)
        home_df = pd.DataFrame(home_df.values.reshape(1, int(len(parsed_home_td))), index=[home_team])
        home_df.rename(
            columns={0: '1', 1: '2', 2: '3', 3: '4', 4: '5', 5: '6', 6: '7', 7: '8', 8: '9', 9: '10', 10: '11',
                     11: '12', 12: '13', 13: '14', 14: '15', 15: '16', 16: '17', 17: '18', 18: '19', 19: '20', 20: '21',
                     21: '22', 22: '23', 23: '24', 24: '25', 25: '26', home_df.columns[-3]: 'R',
                     home_df.columns[-2]: 'H', home_df.columns[-1]: 'E'}, inplace=True)
        # Tags each game with the local time it started at, for sorting doubleheaders in the correct order
        scorebox_meta = game_soup.find_all('div', {'class': 'scorebox_meta'})
        scorebox_meta = scorebox_meta[0].find_all('div')
        parsed_scorebox_meta = parse(scorebox_meta)
        start_time = [item for item in parsed_scorebox_meta if 'Start Time' in item]
        start_time = start_time[0].split('Start Time: ')[1]
        start_time = start_time.split(' Local')[0]
        start_time_minutes = int(start_time.split(':')[1][:2]) / 60
        start_time_hour = start_time.split(':')[0]
        start_time_hour = int(start_time_hour)
        if start_time_hour == 12:
            start_time_hour = 0
        elif start_time_hour == 11:
            start_time_hour = -1
            start_time_hour == -1
        elif start_time_hour == 10:
            start_time_hour = -2
        start_time_number = start_time_hour + start_time_minutes
        ### Combining Section
        # Combines the away and home dataframes to create the full inning-by-inning scoreboard for the game
        # Adds total runs ('Total R') and first 5 inning runs ('1st5 R') columns and places them at
        # the beginning of DataFrame
        full_df = pd.concat([away_df, home_df])
        full_df['Local Start Time'] = start_time_number
        total_runs_col = full_df['R']
        full_df.insert(loc=0, column='Total R', value=total_runs_col)
        first5_runs_col = full_df['1'] + full_df['2'] + full_df['3'] + full_df['4'] + full_df['5']
        full_df.insert(loc=0, column='1st5 R', value=first5_runs_col)
        # Appends the individual game's scoreboard to the existing dataframe of the scoreboards of all
        ### the other games
        all_games_df = all_games_df.append(full_df)
    # End of 'for loop'.
    #
    # Fills all occurrences of NaN with '-' and all occurrences of 'X' with '-' so all half innings that
    # a team didn't bat for are all now '-'
    all_games_df = all_games_df.fillna('-')
    all_games_df = all_games_df.replace('X', '-')
    # Moves the runs ('R'), hits ('H'), and errors ('E') columns to the end of the scoreboard
    # If some games go to extra innings, these columns are no longer at the end, and this code fixes that issue
    r_df = all_games_df.pop('R')
    h_df = all_games_df.pop('H')
    e_df = all_games_df.pop('E')
    all_games_df['R'] = r_df
    all_games_df['H'] = h_df
    all_games_df['E'] = e_df
    # Creates a BeautifulSoup object to be used to find the date that the scores are being displayed from
    # (e.g. Apr 5, 2022)
    date = soup.find_all('span', {'class': 'button2 current'})
    # Parses the date from the page the box scores were pulled from into a Python string, then splits it
    # and gets the individual day, month, year in the desired format
    parsed_date = parse(date)
    parsed_date = parsed_date[0]
    parsed_date_split = parsed_date.split(' ')
    month = parsed_date_split[0]
    day1 = parsed_date_split[1].split(',')[0]
    year1 = parsed_date_split[2][2:]
    month_number = list(calendar.month_abbr).index(month)
    # Stamps the DataFrame with the date from the page the box scores were pulled from.
    all_games_df['Date'] = str(month_number) + '.' + day1 + '.' + year1
    # Creates a DataFrame with only the 1st 5 runs, total runs, and date column and copies it to the
    # clipboard and prints it
    # Tells the user the date of the page the box scores were pulled from,
    # so the user can verify this is the date they were looking for
    # Sorts the games by the hour of the local start time to ensure the first doubleheader game
    # comes before the second doubleheader game
    all_games_condensed = all_games_df[['1st5 R', 'Total R', 'Date', 'Local Start Time']]
    print('\n')
    all_games_condensed = all_games_condensed.sort_values(by=['Local Start Time'], kind='mergesort')
    all_games_condensed = all_games_condensed[['1st5 R', 'Total R', 'Date']]
    print(all_games_condensed)
    print('\nBaseball Reference Scores From: ' + parsed_date)
    all_games_condensed.to_clipboard()
    # Warns user if the table on BBRef doesn't have same date as you want (today's date)
    # This can occur if the scores for the desired day aren't uploaded yet (i.e. if you are looking for today's scores
    # but they aren't up yet, the web address will redirect you to yesterday's scores and pull from there)
    if day != day1:
        print('\nWARNING: Baseball Reference table date does not match desired date')


### Section that creates the necessary dates to be passed to the scores_compiler function, depenidng on
### which button is pressed by the user
# Creates the day, month, and year for yesterday's date to be passed to the scores_compiler function
if event == "Yesterday's Scores":
    yesterday_date = datetime.date.today() - datetime.timedelta(days=1)
    yesterday_month = yesterday_date.strftime('%-m')
    yesterday_day = yesterday_date.strftime('%-d')
    yesterday_year = yesterday_date.strftime('%Y')
    full_date = yesterday_month + '.' + yesterday_day + '.' + yesterday_year
    scores_compiler(yesterday_month, yesterday_day, yesterday_year)
# Creates the day, month, and year for today's date to be passed to the scores_compiler function
elif event == "Today's Scores":
    today_date = datetime.date.today()
    today_month = today_date.strftime('%-m')
    today_day = today_date.strftime('%-d')
    today_year = today_date.strftime('%Y')
    full_date = today_month + '.' + today_day + '.' + today_year
    scores_compiler(today_month, today_day, today_year)
# Creates the day, month, and year for a user-entered custom date to be passed to the scores_compiler function
elif event == "Submit Scores Request":
    custom_month = values['Month Scores']
    month_full = calendar.month_name[int(values['Month Scores'])]
    custom_day = values['Day Scores']
    custom_year = values['Year Scores']
    full_date = month_full + ' ' + custom_day + ', 20' + custom_year
    scores_compiler(custom_month, custom_day, custom_year)




