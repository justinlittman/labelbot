import requests
import csv
from io import StringIO
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

auth = tweepy.OAuthHandler(config.consumer_key, config.consumer_secret)
auth.set_access_token(config.access_token, config.access_token_secret)

api = tweepy.API(auth)

class_type_cache = dict()


def retrieve_colas(date_from, date_to, class_type_from, class_type_to):
    data = {
        'searchCriteria.dateCompletedFrom': date_from,
        'searchCriteria.dateCompletedTo': date_to,
        'searchCriteria.classTypeFrom': class_type_from,
        'searchCriteria.classTypeTo': class_type_to
    }

    search_resp = requests.post('https://www.ttbonline.gov/colasonline/publicSearchColasBasicProcess.do?action=search',
                                data=data)
    search_resp.raise_for_status()
    save_results_resp = requests.get(
        'https://www.ttbonline.gov/colasonline/publicSaveSearchResultsToFile.do?path=/publicSearchColasBasicProcess',
        cookies=search_resp.cookies)
    save_results_resp.raise_for_status()

    reader = csv.DictReader(StringIO(save_results_resp.text))

    colas = []
    for row in reader:
        colas.append((row['TTB ID'].strip('\''), row['Fanciful Name'], row['Brand Name'],
                      lookup_class_type(row['Class/Type'])))

    return colas


def retrieve_cola_detail(ttb_id):
    detail_resp = requests.get(
        'https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid={}'.format(ttb_id))
    detail_resp.raise_for_status()

    doc = BeautifulSoup(detail_resp.text, 'html.parser')

    company = list(doc.find_all('div', class_='data')[6].strings)[0].strip(' \t\r\n')
    if ',' in company:
        company = company.split(',')[0]

    img = doc.find_all('img')[1]
    src = img['src']
    filename = re.search(r'filename=(.+)&', src).group(1)
    return company, filename, 'https://www.ttbonline.gov' + src, detail_resp.cookies


def retrieve_image(filename, url, cookies):
    image_resp = requests.get(url, stream=True, cookies=cookies)
    image_resp.raise_for_status()
    with open(os.path.join(config.images_dir, filename), 'wb') as file:
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


def main(day, class_type_code_ranges, test=False, limit=0, delay=config.delay_secs):
    if os.path.exists(config.images_dir):
        shutil.rmtree(config.images_dir)
    os.makedirs(config.images_dir)

    colas = []
    for class_type_code_range in class_type_code_ranges:
        colas.extend(retrieve_colas(day, day, class_type_code_range[0], class_type_code_range[1]))

    if colas:
        random.shuffle(colas)
        for count, (ttb_id, fanciful_name, brand_name, class_type) in enumerate(colas):
            if limit and limit == count:
                break
            if count != 0 and not test:
                sleep(delay)
            company, image_filename, image_url, cookies = retrieve_cola_detail(ttb_id)
            media_ids = []
            if not test:
                retrieve_image(image_filename, image_url, cookies)
                with open(os.path.join('images', image_filename), 'rb') as file:
                    upload_resp = api.media_upload(image_filename, file=file)
                    media_ids.append(upload_resp.media_id_string)
            class_type_str = ''
            if class_type:
                class_type_str = ', a {}'.format(class_type.lower())
                if class_type[0] in ['a', 'e', 'i', 'o', 'u']:
                    class_type_str = ', an {}'.format(class_type.lower())
            name = brand_name
            if fanciful_name:
                name = '{} / {}'.format(brand_name, fanciful_name)
            status = '{} was approved for {}{}. Full application: ' \
                     'https://www.ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid={}'.format(
                        company, name, class_type_str, ttb_id)
            print('{}: Tweeted {}'.format(day, status))
            if not test:
                api.update_status(status=status, media_ids=media_ids)
    else:
        print('{}: No tweets'.format(day))


if __name__ == '__main__':
    parser = argparse.ArgumentParser("label_bot")
    day = (datetime.date.today()+ datetime.timedelta(days=-3)).strftime('%m/%d/%Y')
    parser.add_argument('class_type_range', nargs='+', help='Class type code ranges, e.g., 900-909.')
    parser.add_argument('--day', help='Day to retrieve labels for. Default is {}.'.format(day), default=day)
    parser.add_argument('--delay', type=int, help='Seconds between posting. Default is {}.'.format(config.delay_secs),
                        default=config.delay_secs)
    parser.add_argument('--limit', type=int, default='0', help='Maximum number of posts.')
    parser.add_argument('--test', action='store_true')

    args = parser.parse_args()

    class_type_ranges = []
    for class_type_range in args.class_type_range:
        class_type_ranges.append(class_type_range.split('-'))

    main(args.day, class_type_ranges, test=args.test, limit=args.limit, delay=args.delay)
