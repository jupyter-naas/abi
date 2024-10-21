import pickle
import os
from unidecode import unidecode
from difflib import SequenceMatcher
import re
from datetime import datetime, timedelta
import naas_python
from naas_drivers import linkedin
import shutil
import pandas as pd
import pycountry
import hashlib
import requests
from googlesearch import search


# Search LinkedIn URL (CSE)
def __search_linkedin_url(
    keyword=None,
    pattern=None
):
    if keyword == "" or pattern == "":
        return {}
    url = "https://google-search-api.default.nebari.dev.naas.ai/search"
    data = {
        "keyword": keyword,
        "pattern": pattern,
        "start_index": 0
    }
    res = requests.post(url, json=data)
    if res.status_code == 200:
        return res.json()
    return {}

# keyword = "Porsche"
# pattern = f"https:\/\/.+.linkedin.com\/company|school|showcase\/.([^?])+" 
# __search_linkedin_url(keyword, pattern)


# Search LinkedIn URL (google package)
def search_linkedin_url(
    keyword,
    urls,
    query=None,
    output_dir="."
):
    # Init
    url = "NA"
    pattern = f"https:\/\/.+.linkedin.com\/company|school|showcase\/.([^?])+"
    
    # Use googlesearch package or custom function naas
    if pload(output_dir, "googlesearch_error"):
        linkedin_url = __search_linkedin_url(keyword, pattern)
        if linkedin_url.get("linkedin_url"):
            url = linkedin_url.get("linkedin_url")
    else: 
        try:
            # Create query
            if query is None:
                query = f"{keyword.replace(' ', '+')}+LinkedIn+company"
            print("Google query: ", query)
            # Search in Google
            for i in search(query, tld="com", num=10, stop=10, pause=2):
                result = re.search(pattern, i)
                # Avoid Too Many Requests Error
                time.sleep(5)
                # Return value if result is not None
                if result != None:
                    url = i
                    break
        except Exception as e:
            print(e)
            pdump(output_dir, "HTTP Error 429: Too Many Requests", "googlesearch_error")
            
    # Add URL to dict
    urls[keyword] = url
    
    # Save URL
    pdump(output_dir, urls, "org_lk_urls")
    return url

# keyword = "Porsche"
# urls = {}
# search_linkedin_url(keyword, urls)


# Get LinkedIn ID from URL
def get_linkedin_id_from_url(url):
    splits = ["/in/", "/company/", "/school/", "/showcase/"]
    for split in splits:
        if split in url:
            return url.split(split)[1].split("/")[0]
        
# url = "https://www.linkedin.com/in/florent-ravenel"      
# get_linkedin_id_from_url(url)


# Get country name
def get_country_name(country_code):
    country_name = "Not Found"
    if str(country_code) not in ["None", "OO"] :
        try:
            country = pycountry.countries.get(alpha_2=country_code)
            country_name = country.name
        except Exception as e:
            print(e)
    return country_name

# country_code = "FR"
# get_country_name(country_code)


# Pickle dump
def pdump(
    output_dir,
    object_to_dump,
    file_to_dump_to,
    extension="pickle"
):
    os.makedirs(output_dir, exist_ok=True)
    file_name = file_to_dump_to.split(f".{extension}")[0]
    file_path = os.path.join(output_dir, f'{file_name}.{extension}')
    histo_path = os.path.join(output_dir, f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{file_name}.{extension}')
    with open(file_path, 'wb') as file:
        pickle.dump(object_to_dump, file)
    shutil.copy(file_path, histo_path)
    
    
# Pickle load    
def pload(
    output_dir,
    file_to_load_from,
    extension="pickle"
):
    file_name = file_to_load_from.split(f".{extension}")[0]
    file_path = os.path.join(output_dir, f'{file_name}.{extension}')
    try:
        with open(file_path, 'rb') as file:
            return pickle.load(file)
    except:
        return None
    
    
# Store tables   
def save_data(
    obj,
    dl_dir,
    entity_name,
    file_name,
):
    # Get entity code
    entity_code = unidecode(entity_name.lower().replace(" ", "_").replace(".", ""))
    
    # Create directory path
    dir_path = os.path.join(dl_dir, entity_code, "tables", file_name)
    
    # Save in pickle
    pdump(dir_path, obj, file_name)
    
    
# Send data to Gsheet    
def send_data_to_gsheet(
    df: pd.DataFrame,
    df_init: pd.DataFrame, 
    spreadsheet_url: str, 
    sheet_name: str, 
    chunck_size: int = 100000
):
    """
    This function compares two dataframes and if they are different, sends the data from the second dataframe to a Google Sheet.

    :param df: The main dataframe to be sent to Google Sheet.
    :param df_init: The initial dataframe to be compared with the main dataframe.
    :param spreadsheet_url: The URL of the Google Sheet to send data to.
    :param sheet_name: The name of the sheet in the Google Sheet to send data to.
    :param chunck_size: The size of the chunks to split the data into for sending. Default is 100000.
    """
    # Compare dataframes
    df_check = pd.concat([df.astype(str), df_init.astype(str)]).drop_duplicates(keep=False)
    
    # Update or Do nothing
    if len(df_check) > 0:
        df_size = len(df) * len(df.columns)
        if df_size < chunck_size:
            gsheet.connect(spreadsheet_url).send(sheet_name=sheet_name, data=df, append=False)
            print(f"✅ DataFrame successfully sent to Google Sheets!")
        else:
            max_rows = int(chunck_size / len(df.columns))
            start = 0
            limit = start + max_rows
            gsheet.connect(spreadsheet_url).send(sheet_name=sheet_name, data=df[start:limit], append=False)
            print(f"✅ Rows {start} to {limit} successfully added to Google Sheets!")
            start += max_rows
            while start < len(df):
                limit = start + max_rows
                if limit > len(df):
                    limit = len(df)
                gsheet.connect(spreadsheet_url).send(sheet_name=sheet_name, data=df[start:limit], append=True)
                print(f"✅ Rows {start} to {limit} successfully added to Google Sheets!")
                start += max_rows
    else:
        print("Noting to update in Google Sheets!")

        
def are_identical(string1, string2):
    string1 = remove_accent(string1)
    string2 = remove_accent(string2)
    # Create a SequenceMatcher object
    matcher = SequenceMatcher(None, string1, string2)
    
    # Get the ratio of similarity between the two strings
    similarity_ratio = matcher.ratio()
    # If the ratio is 1.0, the strings are identical
    if similarity_ratio > 0.9:
        return True
    else:
        return False

    
def find_crm_match(
    df,
    col_crm,
    value
):
    crm = False
    for x in df[col_crm].unique():
        if are_identical(value, str(x)):
            crm = True
            break
    return crm


def format_number(num):
    return str("{:,.0f}".format(abs(num))).replace(",", " ")


def get_dict_from_df(
    df,
    column_name,
    key,
    file,
    output_dir,
    force_update=True
):
    data = {}
    if column_name in df.columns:
        data = sm.pload(output_dir, file)
        if data is None or force_update:
            df = df[~df[key].isin(["TBD", "NA"])]
            data = df[~df[column_name].isin(["TBD"])].set_index(key)[column_name].to_dict()
            sm.pdump(output_dir, data, file)
        else:
            if 'TBD' in data.keys():
                del data['TBD']
    return data


# Get LinkedIn data
def get_linkedin_data(
    linkedin_url,
    linkedin_dir,
    data_type="top_card",
    li_at=None,
    JSESSIONID=None,
    sm=None,
):
    # Get secrets
    if not li_at:
        li_at = naas_python.secret.get("li_at").value
    if not JSESSIONID:
        JSESSIONID = naas_python.secret.get("JSESSIONID").value
    # Create ID
    if "/in/" in linkedin_url:
        linkedin_id = linkedin_url.split("/in/")[1].split("/")[0]
    else:
        linkedin_id = linkedin_url.split("/company/")[1].split("/")[0]
    df = sm.pload(linkedin_dir, f"{linkedin_id}_linkedin_{data_type}")
    if df is None:
        try:
            if data_type == "top_card":
                df = linkedin.connect(li_at, JSESSIONID).profile.get_top_card(linkedin_url)
            elif data_type == "identity":
                df = linkedin.connect(li_at, JSESSIONID).profile.get_identity(linkedin_url)
            elif data_type == "network":
                df = linkedin.connect(li_at, JSESSIONID).profile.get_network(linkedin_url)
            elif data_type == "contact":
                df = linkedin.connect(li_at, JSESSIONID).profile.get_contact(linkedin_url)
            elif data_type == "resume":
                df = linkedin.connect(li_at, JSESSIONID).profile.get_resume(linkedin_url)
            elif data_type == "company_info":
                df = linkedin.connect(li_at, JSESSIONID).company.get_info(linkedin_url)
            sm.pdump(linkedin_dir, df, f"{linkedin_id}_linkedin_{data_type}")
        except Exception as e:
            print(e)
            df = pd.DataFrame()
    return df
