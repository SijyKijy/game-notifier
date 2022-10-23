import requests
import random
import os
from bs4 import BeautifulSoup
import cloudscraper
from github import Github

try:
    GIST_ID = os.environ["GIST_ID"]
    GH_TOKEN = os.environ["GH_TOKEN"]
    WEBHOOK_PATH = os.environ["WEBHOOK_PATH"]
except KeyError:
    print('Error when getting variables')
    raise

githubApi = Github(GH_TOKEN)

def ConvertPageToGame(game):
    elements = game.select('div.header-h1 > a, div.short-story > div.maincont > div, div.short-story > div.maincont > div > p > a')
    
    if(not elements):
        return None
    
    return {
        'Id': elements[1].get('id')[8:], # Example: 'news-id-5189'
        'Title': elements[0].get_text(strip=True),
        'Url': elements[0].get('href'),
        'PhotoUrl': elements[2].get('href') if 2 < len(elements) else None
    }

def ConvertGameToEmbed(game):
    title = game['Title']
    url = game['Url']
    photoUrl = game['PhotoUrl']
    return {
        'title': f'**{title}**',
        'url': url,
        'thumbnail': {
            'url': photoUrl
        },
        'color': random.randint(1, 16777215)
    }

def GetPage():
    print('Get page')
    scraper = cloudscraper.create_scraper(delay=10, browser='chrome')
    response = scraper.get('https://freetp.org/')
    if response.status_code != 200:
        raise Exception('Error when getting page')
    return response.content

def GetGames():
    print('Get games')
    page = GetPage()
    soup = BeautifulSoup(page,'html.parser')
    elements = soup.select('#dle-content > div.base')
    return list(filter(lambda g: g, map(ConvertPageToGame, elements)))

def GetNewGames(games, lastId):
    print('Get new games')
    index = next((index for (index, d) in enumerate(games) if d["Id"] == lastId), None)
    return games[:index]

def GetLastId():
    print('Get last id')
    gist = githubApi.get_gist(GIST_ID)
    return gist.description

def SaveId(newId):
    print('Save new id')
    gist = githubApi.get_gist(GIST_ID)
    gist.edit(newId)

def Notify(games):
    print('Notify')
    embeds = list(map(ConvertGameToEmbed, games))
    webhookContent = {
        'username': 'FreeTP Notifier',
        'avatar_url': 'https://freetp.org/templates/freetp2/bullet_energy/images/noavatar.png',
        'content': 'Новенькие руководства:',
        'embeds': embeds
    }

    requests.post(f'https://discord.com/api/webhooks/{WEBHOOK_PATH}', json = webhookContent)

def Start():
    lastId = GetLastId()
    games = GetGames()
    if(not games):
        raise Exception('No games found')

    newId = games[0]['Id']
    if (lastId == newId):
        print('New games not found')
        return

    print('Games founded')
    newGames = GetNewGames(games, lastId)
    print(f'New games founded (Count: {len(newGames)})')
    
    Notify(newGames)
    SaveId(newId)
    
if __name__ == "__main__":
    Start()