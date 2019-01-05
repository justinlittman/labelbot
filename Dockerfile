FROM python:3.6
MAINTAINER Justin Littman <justinlittman@gmail.com>

RUN apt-get update && apt-get install chromium chromedriver -y

ADD requirements.txt /labelbot/
RUN pip install -r /labelbot/requirements.txt

ADD label_bot.py /labelbot/
ADD example.config.py /labelbot/config.py

WORKDIR /labelbot
ENTRYPOINT ["python", "label_bot.py", "--working-dir", "/labelbot_working"]
CMD ["900-909", "950-959"]