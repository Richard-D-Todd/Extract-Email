import glob
import os
import email
from email.policy import default
from requests_html import HTML
import pandas as pd
import numpy as np
import datetime
import re
import sqlalchemy
from sqlalchemy import create_engine
import credentials
import configparser

# Define functions
def insert_order_num_col(df):
    """
    This function adds the order number to the beginning of a dataframe (df)
    """
    df = df.insert(0, 'order_number', order_number)
    return df

def convert_price_col(df, col_name):
    """
    This function casts the price column to a float
    """
    df[col_name] = pd.to_numeric(df[col_name], errors="raise", downcast="float")
    return df[col_name]

def convert_quant_col(df, col_name):
    """
    Ths function converts the quantity column to numeric values using the pandas method, to _numeric. 
    Since the quantity could be a weight with a kg at the end of the value, this function will result in that row becoming a NaN, 
    then converting this NaN to a value of one, before converting to an int.
    """
    df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
    df[col_name] = df[col_name].fillna(1)
    df[col_name] = df[col_name].astype('int')
    return df[col_name]

def calc_unit_price_col(df):
    """
    This function calculates a unit price column for the dataframe df
    """
    df['unit_price'] = df['price'] / df['quantity']
    return df['unit_price']

def save_to_csv(filepath):
    """
    This function saves all the dataframes created as csv files.
    """
    path = os.path.join(filepath, str(delivery_date))
    os.makedirs(path)
    filename_delivered = path + '\delivered_items_' + str(delivery_date) + '.csv'
    df_delivered.to_csv(filename_delivered, index=False)

    if unavailable_present == True:
        filename_unavail = path + r'\unavailable_items_' + str(delivery_date) + '.csv'
        df_unavail.to_csv(filename_unavail, index=False)
    else:
        print("no unavailable items")
        filename_unavail = None

    filename_order_details = path + '\order_details_' + str(delivery_date) + '.csv'
    df_order_details.to_csv(filename_order_details, index=False)

    return print(
        f"CSV files saved in directory: {path}\n"
        f"delivered    : {filename_delivered}\n"
        f"unavailable  : {filename_unavail}\n"
        f"order details: {filename_order_details} ")

def create_sqlalchemy_engine():
    """
    This function creates a sqlalchemy engine with the credentials stored in the credentials.py file
    """
    config = configparser.ConfigParser()
    config.read('database.ini')
    username = config['postgresql']['user']
    password = config['postgresql']['password']
    database = config['postgresql']['database']
    con_string_local = 'postgresql+psycopg2://{}:{}@localhost/{}?gssencmode=disable'.format(username, password, database)
    con_string_heroku = 'postgres://gcryjyqfmmbiie:cd7eefd50e77a028894d735d89be4fdab77aa61643183e027f310354ebe9ba1d@ec2-54-247-89-181.eu-west-1.compute.amazonaws.com:5432/ddvcbrmstdole4'
    engine_local = create_engine(con_string_local)
    engine_ext = create_engine(con_string_heroku)
    print("Local DB: {}".format(con_string_local))
    print("Heroku DB: {}".format(con_string_heroku))
    return engine_local, engine_ext

def insert_into_db():
    """
    This functions inserts the df created into the groceries database
    """
    df_order_details.to_sql('order_details', con = engine_local, if_exists='append', index=False)
    df_order_details.to_sql('order_details', con = engine_ext, if_exists='append', index=False)
    df_delivered.to_sql('delivered_items', con = engine_local, if_exists='append', index=False)
    df_delivered.to_sql('delivered_items', con = engine_ext, if_exists='append', index=False)
    if unavailable_present == True:
        df_unavail.to_sql('unavailable_items', con = engine_local, if_exists='append', index=False)
        df_unavail.to_sql('unavailable_items', con = engine_ext, if_exists='append', index=False)
    else:
        print("No unavailable items to load to database")
    return print("Finished insert into database")

def remove_blank_and_headings(element):
    """Removes blank lines and heading titles from the categories.txt file from a list"""
    with open('categories.txt') as cat:
        categories = cat.read().splitlines()
    remove_list = ['Quantity', 'Price', None]
    # concat the categories list to the remove list
    remove_list = remove_list + categories
    if element in remove_list:
        return False
    else:
        return element

# Prompts for the directory containing the eml email files
directory = input("What is the path of the directory containing the email files?",)
files = glob.glob(directory + '\*.eml')

# Prompts user whether to export to csv or not. 
save_option = input('Do you want to save to CSV? (Y/N)',).upper()
while True:
    if save_option == 'Y':
        filepath_csv = input('Where is the directory you want to save CSV files to?',)
        break
    elif save_option == 'N':
        print("Will not export CSVs")
        break
    else:
        print('Incorrect input')
        break

# Prompts user whether to export to postgresql database or not
while True:
        insert_option = input('Do you want to export to groceries database? (Y/N)',)
        insert_option = insert_option.upper()

        if insert_option == 'Y':
            print('Will export to database')
            engine_local, engine_ext = create_sqlalchemy_engine()
            break
        elif insert_option == 'N':
            print('Will not export to database')
            break
        else:
            print('Incorrect input')

# For loop processes each file in the directory specified above, the number_files variable counts the number of files processed
number_files = 0
for file in files:
    # Get filename
    file_name = os.path.abspath(file)
    number_files += 1
    print("The email filename is: {},\nthis is file number: {}".format(file_name, number_files))
    
    # Use functions to do this

    #Open eml email file
    with open(file_name, 'r') as file:
        msg = email.message_from_file(file, policy=default)



    # Extract body of email message and convert to HTML
    body = msg.get_payload(decode=True)
    html = HTML(html=body)
    match = html.find('tr')

    # Remove special characters and seperate email body into list of lines
    content = match[0].text
    content = re.sub(r'[^\x00-\x7f]',r'', content)
    lines = content.splitlines()

    #Checking for subject line
    if msg['subject'] == 'Your updated ASDA Groceries order':
        # Extract the order number, delivery date, subtotal and total
        order_number = lines[1]
        delivery_date_str = lines[3]
        total_str = lines[lines.index('Total') + 1]
        subtotal_str = lines[lines.index('Subtotal*') + 5]

        # Converting delivery date to a date object
        delivery_date_str = delivery_date_str[0:11]
        delivery_date = datetime.datetime.strptime(delivery_date_str, '%d %b %Y').date()
        

        # Start_substitutes finds the index of the line containing the Substitutes header. Since there may not be substitutes
        # this is set up in a try, except format. the variable substitutions_present tracks if a file has subs or not
        try:
            start_substitutes = lines.index('Substitutes')
            # This groups the lines into a new substitutes list which is made up of a tuple of 4 elements
            i = start_substitutes + 3
            substitutes = []
            while len(lines[i]) > 0 :
                substitutes.append((lines[i], lines[i + 1][19:], lines[i + 2], lines[i + 3]))
                i += 4
            substitutions_present = True
        except:
            print("No substitutions")
            substitutions_present = False

        # find the start of the unavailable section and pack into a list of tuples
        try:
            start_unavailable = lines.index('Unavailable')
            i = start_unavailable + 3
            unavailable = []
            while len(lines[i]) > 0 :
                unavailable.append((lines[i], lines[i + 1], lines[i + 2]))
                i += 3
            unavailable_present = True
        except:
            print("No unavailable items")
            unavailable_present = False


        # We can find the start and end of the ordered section then create a list
        start_ordered = lines.index('Ordered')
        end_ordered = lines.index('Multibuy Savings')

        i = start_ordered + 3
        ordered = []
        while i < end_ordered :
            ordered.append(lines[i])
            i += 1

        # Remove blank list elements
        ordered = list(filter(remove_blank_and_headings, ordered))

        # Create a new list without the category headings, if more headings need defining, add them to categories.txt
        with open('categories.txt') as cat:
            categories = cat.read().splitlines()

        ordered_items = []
        for element in ordered:
            if element in categories:
                pass
            else:
                ordered_items.append(element)

        # Create a list of tuples for the ordered items
        i = 0
        ordered_clean = []
        while i < len(ordered_items) :
            ordered_clean.append((ordered_items[i], ordered_items[i + 1], ordered_items[i + 2]))
            i += 3
    elif msg['subject'] == 'Order Receipt':
        # Remove reference to 'You still get your discount' if present
        try:
            remove_index = lines.index('You still get your discount')
            lines.pop(remove_index)
        except:
            pass
        
        # The order number is sometimes called order receipt, below try block looks for either
        try:
            order_number = lines[lines.index('Order Receipt:') + 1]
        except:
            order_number = lines[lines.index('Order Number:') + 1]
        total_str = lines[lines.index('Order total') + 1]
        subtotal_str = lines[lines.index('Groceries') + 1]
        
        # Get date string from the email metadata and convert the delivery date to a date object
        delivery_date_str = msg['date'][0:16]
        delivery_date = datetime.datetime.strptime(delivery_date_str, '%a, %d %b %Y').date()

        we_sent_lines = []
        not_available_lines = []
        i = 0
        subs_end = lines.index('Your order')

        # Checking for substitutions and unavailable items
        while i < subs_end :
            if lines[i] == 'We sent':
                we_sent_lines.append(i)
                i += 1
            elif lines[i] == 'Not available':
                not_available_lines.append(i)
                i += 1
            else:
                i += 1

        # Create substitutes list if substitutes are present
        # Remove reference to 'You still get your discount' if present
        try:
            remove_index = lines.index('You still get your discount')
            lines.pop(remove_index)
        except:
            pass

        if len(we_sent_lines) > 0:
            substitutes = []
            # lines[i - 2] gives the original item, lines[i + 1], gives the substitution
            # retrieveing the first character, lines[i + 1][0], gives the quantity
            # line[i + 2] gives the price
            for i in we_sent_lines:
                substitutes.append((lines[i + 1][4:], lines[i - 2][4:], lines[i + 1][0], lines[i + 2]))
                substitutions_present = True  
        else:
            substitutions_present = False

        # Create unavailable list if unavailable itemss are present
        if len(not_available_lines) > 0:
            unavailable = []
            for i in not_available_lines:
                # lines[i - 1] gives the unavailable item
                # lines[i - 1][0] gives the first character which is the quantity
                # lines[i + 1] gives the price
                unavailable.append((lines[i - 1][4:], lines[i - 1][0], lines[i + 1])) 
                unavailable_present = True
        else:
            unavailable_present = False   

        # Create ordered items list
        ordered_start = lines.index('Your order')
        ordered_end = lines.index('Groceries')
        ordered = []
        i = ordered_start + 1

        while i < ordered_end:
            ordered.append(lines[i])
            i += 1

        # Removing blank lines and headings
        ordered = list(filter(remove_blank_and_headings, ordered))

        # Create a list of tuples for the ordered items
        i = 0
        ordered_clean = []

        while i < len(ordered) :
            ordered_clean.append((ordered[i], ordered[i + 1], ordered[i + 2]))
            i += 3
    else:
        print('Subject of email not recognised, can\'t identify the email template')
        break

    #Converts subtotal and total to floats
    subtotal = float(subtotal_str)
    total = float(total_str)
    

    # Create a dictionary to store the order details
    order_dict = {'order_number': order_number,'delivery_date': delivery_date, 'subtotal': subtotal, 'total': total}

    #Create and format the substitutions dataframe
    if substitutions_present == True:
        df_subs = pd.DataFrame(substitutes, columns = ['item', 'substituting', 'quantity', 'price'])
        col_titles_sub = ['item', 'substituting', 'price', 'quantity']
        df_subs = df_subs.reindex(columns=col_titles_sub)
        insert_order_num_col(df_subs)
        df_subs.insert(2, 'substitution', True)  
        convert_price_col(df_subs, 'price')
        convert_quant_col(df_subs, 'quantity')
        calc_unit_price_col(df_subs)
    else:
        pass

    # Create and format the unavailable items dataframe
    if unavailable_present == True:
        df_unavail = pd.DataFrame(unavailable, columns = ['item', 'quantity', 'price'])
        insert_order_num_col(df_unavail)
        convert_quant_col(df_unavail, 'quantity')
        df_unavail = df_unavail.drop(['price'], axis=1)
    else:
        pass

    # Create ordered and order details DataFrames 
    df_order_details = pd.DataFrame.from_dict([order_dict])
    df_order_details['delivery_date'] = pd.to_datetime(df_order_details['delivery_date'])

    # Swap price and quantity columns for the ordered df
    df_ordered = pd.DataFrame(ordered_clean, columns = ['item', 'quantity', 'price'])
    col_titles_ordered = ['item', 'price', 'quantity']
    df_ordered = df_ordered.reindex(columns=col_titles_ordered)

    # Formatting the ordered items df
    insert_order_num_col(df_ordered) # insert the order number at the start of the df
    df_ordered.insert(2, 'substitution', False) # insert a substitution column with False as the values
    df_ordered.insert(3, 'substituting', 'None') # insert a substitution column with the string None as the values
    convert_price_col(df_ordered, 'price') # convert price column to float
    convert_quant_col(df_ordered, 'quantity') # convert quantity column to int
    calc_unit_price_col(df_ordered) # calculate the unit price for each row

    # Joining ordered and substitution dataframes (if substitution df exists)
    if substitutions_present == True:
        df_delivered = df_subs.append(df_ordered, ignore_index=True)
    else:
        df_delivered = df_ordered

    #Save to csv (if y was selected)
    while True:
        if save_option == 'Y':
            save_to_csv(filepath_csv)
            break
        elif save_option == 'N':
            print("CSV not saved")
            break
        else:
            print("Incorrect input")

    # Insert into db (if y was selected)
    while True:
        if insert_option == 'Y':
            insert_into_db()
            break
        elif insert_option == 'N':
            print('Not exported to database')
            break
        else:
            print('Incorrect input')
    print(f"Files processed: {number_files}")

# print the total number of email files processed
print(f"Batch completed, {number_files} email files were processed")