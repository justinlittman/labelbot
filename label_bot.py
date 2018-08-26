import requests
import csv
from bs4 import BeautifulSoup
import re
import os
import tweepy
import datetime
import shutil
from time import sleep
import argparse
import random
import config
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

auth = tweepy.OAuthHandler(config.consumer_key, config.consumer_secret)
auth.set_access_token(config.access_token, config.access_token_secret)

api = tweepy.API(auth)

class_type_cache = dict()


def retrieve_colas(date_from, date_to, class_type_from, class_type_to, driver):
    driver.get('https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do')
    driver.find_element_by_name('searchCriteria.dateCompletedFrom').send_keys(date_from)
    driver.find_element_by_name('searchCriteria.dateCompletedTo').send_keys(date_to)
    driver.find_element_by_name('searchCriteria.classTypeFrom').send_keys(class_type_from)
    driver.find_element_by_name('searchCriteria.classTypeTo').send_keys(class_type_to)
    driver.find_element_by_xpath("//input[@value='Search']").click()

    driver.get('https://www.ttbonline.gov/colasonline/publicSaveSearchResultsToFile.do?'
               'path=/publicSearchColasBasicProcess')
    sleep(4)

    colas = []
    with open(os.path.join(config.working_dir, 'SearchResultsFile.csv')) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            colas.append((row['TTB ID'].strip('\''), row['Fanciful Name'], row['Brand Name'],
                          lookup_class_type(row['Class/Type']), row['Origin']))
    return colas


def retrieve_cola_detail(ttb_id, driver):
    driver.get(
        'https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid={}'.format(ttb_id))

    WebDriverWait(driver, 10).until(
        EC.title_is('OMB No. 1513-0020'))
    doc = BeautifulSoup(driver.page_source, 'html.parser')
    company = list(doc.find_all('div', class_='data')[6].strings)[0].strip(' \t\r\n')
    if ',' in company:
        company = company.split(',')[0]
    is_square = False
    for t in doc.stripped_strings:
        m = re.match('Actual Dimensions: ([0-9\.]+) inches W X ([0-9\.]+) inches H', t)
        if m and m.groups()[0] == m.groups()[1]:
            is_square = True
            break
    img = doc.find_all('img')[1]
    src = img['src']
    filename = re.search(r'filename=(.+)&', src).group(1)
    return company, filename, 'https://www.ttbonline.gov' + src, is_square


def retrieve_image(filename, url, session):
    print('Getting {}'.format(url))
    image_resp = session.get(url, stream=True)
    image_resp.raise_for_status()
    with open(os.path.join(config.working_dir, filename), 'wb') as file:
        for chunk in image_resp:
            file.write(chunk)


def lookup_class_type(class_type_code):
    if class_type_code not in class_type_cache:
        data = {
            'searchCriteria.classTypeCode': class_type_code
        }
        lookup_resp = requests.post('https://www.ttbonline.gov/colasonline/lookupProductClassTypeCode.do?action=search',
                                    data=data)
        lookup_resp.raise_for_status()
        doc = BeautifulSoup(lookup_resp.text, 'html.parser')
        td = doc.find('td', width='77%', height='22')
        class_type_cache[class_type_code] = None
        if td:
            class_type_cache[class_type_code] = td.string.lower()
    return class_type_cache[class_type_code]


def main(day, class_type_code_ranges, test=False, limit=0, delay=config.delay_secs, omit_square=False, headless=True):
    if os.path.exists(config.working_dir):
        shutil.rmtree(config.working_dir)
    os.makedirs(config.working_dir)

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('headless')
    options.add_experimental_option('prefs', {'download.default_directory': os.path.abspath(config.working_dir),
                                              "download.prompt_for_download": False})

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
    driver.execute("send_command", {'cmd': 'Page.setDownloadBehavior', 'params': {'behavior': 'allow',
                                                                                  'downloadPath': os.path.abspath(
                                                                                      config.working_dir)}})

    try:
        colas = []
        for class_type_code_range in class_type_code_ranges:
            colas.extend(retrieve_colas(day, day, class_type_code_range[0], class_type_code_range[1], driver))

        tweets = []
        if colas:
            random.shuffle(colas)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/44.0.2403.157 Safari/537.36"
            }
            session = requests.session()
            session.headers.update(headers)

            for cookie in driver.get_cookies():
                c = {cookie['name']: cookie['value']}
                session.cookies.update(c)
            for ttb_id, fanciful_name, brand_name, class_type, origin in colas:
                if limit and limit == len(tweets):
                    break
                company, image_filename, image_url, is_square = retrieve_cola_detail(ttb_id, driver)
                if omit_square and is_square:
                    continue
                retrieve_image(image_filename, image_url, session)

                class_type_str = ''
                if class_type:
                    class_type_str = ', a {}'.format(class_type.lower())
                    if class_type[0] in ['a', 'e', 'i', 'o', 'u']:
                        class_type_str = ', an {}'.format(class_type.lower())
                name = brand_name
                if fanciful_name:
                    name = '{} / {}'.format(brand_name, fanciful_name)
                hashtag = ''
                if origin in config.origin_hashtags:
                    hashtag = ' #{}'.format(config.origin_hashtags[origin])
                status = '{} was approved for {}{}.{} More: ' \
                         'https://www.ttbonline.gov/colasonline/viewColaDetails.do?' \
                         'action=publicFormDisplay&ttbid={}'.format(
                             company, name, class_type_str, hashtag, ttb_id)
                tweets.append((status, image_filename))
    finally:
        driver.close()
        driver.quit()

    if tweets:
        for status, image_filename in tweets:
            print('{}: Tweeted {}'.format(day, status))
            if not test:
                sleep(delay)
                media_ids = []
                with open(os.path.join(config.working_dir, image_filename), 'rb') as file:
                    upload_resp = api.media_upload(image_filename, file=file)
                    media_ids.append(upload_resp.media_id_string)
                api.update_status(status=status, media_ids=media_ids)

    else:
        print('{}: No tweets'.format(day))


if __name__ == '__main__':
    parser = argparse.ArgumentParser("label_bot")
    day = (datetime.date.today() + datetime.timedelta(days=-7)).strftime('%m/%d/%Y')
    parser.add_argument('class_type_range', nargs='+', help='Class type code ranges, e.g., 900-909.')
    parser.add_argument('--day', help='Day to retrieve labels for. Default is {}.'.format(day), default=day)
    parser.add_argument('--delay', type=int, help='Seconds between posting. Default is {}.'.format(config.delay_secs),
                        default=config.delay_secs)
    parser.add_argument('--limit', type=int, default='0', help='Maximum number of posts.')
    parser.add_argument('--omit-square', action='store_true', help='Omit square labels like keg tags')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--headed', help='Use a headed chrome browser', action='store_true')

    args = parser.parse_args()

    class_type_ranges = []
    for class_type_range in args.class_type_range:
        class_type_ranges.append(class_type_range.split('-'))

    main(args.day, class_type_ranges, test=args.test, limit=args.limit, delay=args.delay, omit_square=args.omit_square,
         headless=not args.headed)
