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
    PERP_TOKEN = os.environ["PERP_TOKEN"]
    PERP_MODEL = os.environ["PERP_MODEL"]
    PERP_PROMPT = os.environ["PERP_PROMPT"]
except KeyError:
    print('Error when getting variables')
    raise

githubApi = Github(GH_TOKEN)

def GetPerpDescription(gameName):
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": PERP_MODEL,
        "messages": [
            {
                "role": "system",
                "content": PERP_PROMPT
            },
            {
                "role": "user",
                "content": gameName
            }
        ]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f'Bearer {PERP_TOKEN}'
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.encoding = 'utf-8'
        data = response.json()
        if response.status_code != 200:
            print(f'[GetPerpDescription] Name: \'{gameName}\' Resp: \'{data}\'')
            raise Exception('Error when get perp description')
        return data.choices[0].message.content
    except Exception as e::
        print(f'[GetPerpDescription] Error when get game desc (GameName: \'{gameName}\') (Error: {str(e)})')
        return "¯\_(ツ)_/¯"

def ConvertPageToGame(game):
    elements = game.select('div.header-h1 > a, div.short-story > div.maincont > div, div.short-story > div.maincont > div > p > a')
    comment = game.select('span[style]')
    
    if(not elements):
        return None
    
    return {
        'Id': elements[1].get('id')[8:], # Example: 'news-id-5189'
        'Title': elements[0].get_text(strip=True),
        'Url': elements[0].get('href'),
        'PhotoUrl': elements[2].get('href') if 2 < len(elements) else None,
        'Comment': comment[0].get_text(strip=True) if len(comment) > 0 else None
    }

def ConvertGameToEmbed(game):
    title = game['Title']
    url = game['Url']
    photoUrl = game['PhotoUrl']
    comment = game['Comment']
    desc = GetPerpDescription(title)
    return {
        'title': f'**{title}**',
        'url': url,
        'description': f'{comment}\n---\n{desc}',
        'image': {
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
    try:
        gist = githubApi.get_gist(GIST_ID)
        gist.edit(newId)
    except:
        print(f'Error saving id (NewId: {newId})')

def Notify(game):
    gameTitle = game['Title']
    print(f'[Notify] Notify Title: {gameTitle}')
    embed = ConvertGameToEmbed(game)
    webhookContent = {
        'username': 'FreeTP Notifier',
        'avatar_url': 'https://freetp.org/templates/freetp2/bullet_energy/images/noavatar.png',
        'content': 'Новенькие руководства:',
        'embeds': [embed]
    }

    response = requests.post(f'https://discord.com/api/webhooks/{WEBHOOK_PATH}', json = webhookContent)
    if response.status_code != 200:
        print(f'[Notify] Req: {webhookContent}')
        print(f'[Notify] Resp: {response.text}')
        raise Exception('Error when notify game')

    print('[Notify] Done')

def Start():
    lastId = GetLastId()
    games = GetGames()
    if(not games):
        print('Games not found')
        return

    newId = games[0]['Id']
    if (lastId == newId):
        print('New games not found')
        return

    print('Games founded')
    newGames = GetNewGames(games, lastId)
    print(f'New games founded (Count: {len(newGames)})')

    for game in newGames:
        try:
            Notify(game)
        except Exception as e:
            print(f"Error when notify: {str(e)}")

    SaveId(newId)
    
if __name__ == "__main__":
    Start()
