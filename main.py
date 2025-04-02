import requests
import random
import os
import re
from bs4 import BeautifulSoup
import cloudscraper
from github import Github
from dotenv import load_dotenv
import asyncio
import json
import aiohttp
from urllib.parse import urlparse

load_dotenv()

try:
    GIST_ID = os.environ["GIST_ID"]
    GH_TOKEN = os.environ["GH_TOKEN"]
    WEBHOOKS_PATH = os.environ["WEBHOOKS_PATH"]
    PERP_TOKEN = os.environ["PERP_TOKEN"]
    PERP_MODEL = os.environ["PERP_MODEL"]
    PERP_PROMPT = os.environ["PERP_PROMPT"]
    PERP_URL = os.environ["PERP_URL"]

    if not all([GIST_ID, GH_TOKEN, WEBHOOKS_PATH, PERP_TOKEN, PERP_MODEL, PERP_PROMPT, PERP_URL]):
        raise KeyError("One or more environment variables are missing")
except KeyError:
    print('Error when getting variables')
    raise

githubApi = Github(GH_TOKEN)
webhook_urls = json.loads(WEBHOOKS_PATH)

excluded_ids = [ 
    ]

def IsUrl(url):
    """Проверяет, является ли строка корректным URL.
    
    Args:
        url: Строка для проверки
        
    Returns:
        bool: True если строка является корректным URL, иначе False
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def GetPerpDescription(gameName):
    """Получает описание игры с использованием Perplexity AI.
    
    Args:
        gameName: Название игры
        
    Returns:
        str: Описание игры или строку-заполнитель при ошибке
    """
    url = PERP_URL
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
        content = data['choices'][0]['message']['content']
        cleaned_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        cleaned_content = re.sub(r'\[\d+\]', '', cleaned_content)
        return cleaned_content
    except Exception as e:
        print(f'[GetPerpDescription] Error when get game desc (GameName: \'{gameName}\') (Error: {str(e)})')
        return "¯\_(ツ)_/¯"

def ConvertPageToGame(game):
    """Преобразует HTML-элемент игры в структурированный объект.
    
    Args:
        game: HTML-элемент игры из BeautifulSoup
        
    Returns:
        dict: Словарь с информацией об игре или None, если элементы не найдены
    """
    elements = game.select('div.header-h1 > a, div.short-story > div.maincont > div, div.short-story > div.maincont > div > p > a')
    comment = game.select('span[style]')
    photoUrl = elements[2].get('href') if len(elements) > 2 and IsUrl(elements[2].get('href')) else None

    if not elements:
        return None

    return {
        'Id': elements[1].get('id')[8:],  # Example: 'news-id-5189'
        'Title': elements[0].get_text(strip=True),
        'Url': elements[0].get('href'),
        'PhotoUrl': photoUrl,
        'Comment': comment[0].get_text(strip=True) if len(comment) > 0 else None
    }

def ConvertGameToEmbed(game):
    """Преобразует игру в формат Discord embed.
    
    Args:
        game: Словарь с информацией об игре
        
    Returns:
        dict: Discord embed объект для отправки в webhook
    """
    title = game['Title']
    url = game['Url']
    photoUrl = game['PhotoUrl']
    comment = game['Comment']
    desc = GetPerpDescription(title)
    
    resultEmbed = {
        'title': f'**{title}**',
        'url': url,
        'description': f'{comment}\n---\n{desc}',
        'color': random.randint(1, 16777215)
    }

    if photoUrl:
        resultEmbed['image'] = {
            'url': photoUrl
        }

    return resultEmbed

def GetPage():
    """Получает HTML-страницу с сайта freetp.org.
    
    Returns:
        bytes: HTML-содержимое страницы
        
    Raises:
        Exception: Если возникла ошибка при получении страницы
    """
    print('Get page')
    try:
        scraper = cloudscraper.create_scraper(delay=10, browser='chrome')
        response = scraper.get('https://freetp.org/')
        if response.status_code != 200:
            raise Exception(f'Invalid response status: {response.status_code}')
        return response.content
    except Exception as e:
        print(f'Error when getting page: {str(e)}')
        raise Exception(f'Error when getting page: {str(e)}')

def GetGames():
    """Получает список всех игр с сайта.
    
    Returns:
        list: Список словарей с информацией об играх
    """
    print('Get games')
    page = GetPage()
    soup = BeautifulSoup(page, 'html.parser')
    elements = soup.select('#dle-content > div.base')
    return list(filter(lambda g: g, map(ConvertPageToGame, elements)))

def GetNewGames(games, lastIds):
    """Определяет новые игры, сравнивая текущие ID с сохраненными.
    
    Args:
        games: Список словарей с информацией об играх
        lastIds: Строка с сохраненными ID игр (через запятую)
        
    Returns:
        list: Список новых игр
    """
    print('Get new games')
    lastIdsList = lastIds.split(',') if ',' in lastIds else [lastIds]
    currentIds = [game["Id"] for game in games[:2]]
    
    if len(currentIds) > 0 and currentIds[0] != lastIdsList[0]:
        index = next((index for (index, d) in enumerate(games) if d["Id"] == lastIdsList[0]), None)
        if index is None:
            return games
        return games[:index]
    elif len(currentIds) > 1 and len(lastIdsList) > 1 and currentIds[1] != lastIdsList[1]:
        index = next((index for (index, d) in enumerate(games[1:], 1) if d["Id"] == lastIdsList[1]), None)
        if index is None:
            return games[1:]
        return games[1:index]
    
    return []

def GetLastId():
    """Получает последние сохраненные ID игр из GitHub Gist.
    
    Returns:
        str: Строка с сохраненными ID игр
    """
    print('Get last id')
    gist = githubApi.get_gist(GIST_ID)
    return gist.description

def SaveId(newIds):
    """Сохраняет новые ID игр в GitHub Gist.
    
    Args:
        newIds: Строка с ID игр для сохранения
    """
    print('Save new id')
    try:
        gist = githubApi.get_gist(GIST_ID)
        gist.edit(newIds)
    except Exception as e:
        print(f'Error saving id (NewIds: {newIds}, Error: {str(e)})')

async def Notify(game):
    """Отправляет уведомление о новой игре в Discord webhooks.
    
    Args:
        game: Словарь с информацией об игре
    """
    gameTitle = game['Title']
    print(f'[Notify] Notify Title: {gameTitle}')
    embed = ConvertGameToEmbed(game)
    webhookContent = {
        'username': 'FreeTP Notifier',
        'avatar_url': 'https://freetp.org/templates/freetp2/bullet_energy/images/noavatar.png',
        'content': 'Новенькие руководства:',
        'embeds': [embed]
    }
    
    async def send_webhook(url, webhookContent):
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.post(url, json=webhookContent) as response:
                    if response.status == 429:
                        retry_after = float(response.headers.get('Retry-After', 1))
                        print(f'[Notify] Rate limited. Retrying after {retry_after} seconds.')
                        await asyncio.sleep(retry_after)
                    elif response.status > 300:
                        print(f'[Notify] Req: {webhookContent}')
                        print(f'[Notify] [{response.status}] Resp: {await response.text()}')
                        raise Exception('Error when notify game')
                    else:
                        break

    async def notify_games(webhook_urls, webhookContent):
        tasks = []
        for url in webhook_urls:
            task = asyncio.create_task(send_webhook(url, webhookContent))
            tasks.append(task)
        await asyncio.gather(*tasks)

    await notify_games(webhook_urls, webhookContent)
    print('[Notify] Done')

def Start():
    lastIds = GetLastId()
    games = GetGames()
    games = [game for game in games if game['Id'] not in excluded_ids]
    if not games:
        print('Games not found')
        return
    
    print(f'Game IDs: {", ".join(str(game["Id"]) for game in games)}')
    
    if len(games) >= 2:
        newIds = f"{games[0]['Id']},{games[1]['Id']}"
    else:
        newIds = games[0]['Id']
    
    if lastIds == newIds:
        print('New games not found')
        return

    print('Games founded')
    newGames = GetNewGames(games, lastIds)
    newGames.reverse()
    print(f'New games founded (Count: {len(newGames)})')

    async def notify_games_async(newGames):
        for game in newGames:
            await Notify(game)

    asyncio.run(notify_games_async(newGames))

    SaveId(newIds)

if __name__ == "__main__":
    Start()
