# labelbot
Twitter bot for tweeting label approvals from [COLA Public Registry](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do).

This bot is currently tweets as [@beerlabelbot](https://twitter.com/beerlabelbot).

## Requirements
* Python 3
* Keys for a [Twitter app](https://apps.twitter.com/)

## Setup
1. Clone this repo.

        git clone https://github.com/justinlittman/labelbot.git
    
2. Install the requirements.

        pip install -r requirements.txt
    
3. Copy example.config.py to config.py.

        cp example.config.py config.py
    
4. Update config.py. This may require that you create a new Twitter app.

5. [Install Chromedriver](https://sites.google.com/a/chromium.org/chromedriver/).
   
   On a Mac, this is:

        brew cask install chromedriver
        
   If already installed, upgrade Chromedriver with:

        brew cask upgrade chromedriver
        
   On Ubuntu, this is:
   
        apt-get install chromium-chromedriver
        
   And then add this to your .profile:
   
        PATH="$PATH:/usr/lib/chromium-browser/"


## Usage

    python label_bot.py 900-909 950-959
    
In this example, 900-909 and 950-959 are the class type code ranges for malt beverages.

For a full set of options, see `python label_bot.py -h`.
