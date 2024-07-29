import unittest
from unittest.mock import patch, MagicMock
import main
import asyncio

class TestMain(unittest.TestCase):
    @patch('main.requests.post')
    def test_GetPerpDescription(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': '"Test Description"'}}]
        }
        result = main.GetPerpDescription('Test Game')
        self.assertEqual(result, 'Test Description')

        mock_post.return_value.status_code = 500
        mock_post.return_value.json.return_value = {}
        result = main.GetPerpDescription('Test Game')
        self.assertEqual(result, "¯\_(ツ)_/¯")

    @patch('main.cloudscraper.create_scraper')
    def test_GetPage(self, mock_create_scraper):
        mock_scraper = MagicMock()
        mock_scraper.get.return_value.status_code = 200
        mock_scraper.get.return_value.content = b'<html></html>'
        mock_create_scraper.return_value = mock_scraper

        result = main.GetPage()
        self.assertEqual(result, b'<html></html>')

        mock_scraper.get.return_value.status_code = 500
        with self.assertRaises(Exception):
            main.GetPage()

    @patch('main.GetPage')
    @patch('main.BeautifulSoup')
    def test_GetGames(self, mock_soup, mock_GetPage):
        mock_GetPage.return_value = b'<html></html>'
        mock_element = MagicMock()
        mock_soup.return_value.select.return_value = [mock_element]

        with patch('main.ConvertPageToGame', return_value={'Id': '1'}):
            result = main.GetGames()
            self.assertEqual(result, [{'Id': '1'}])

    def test_GetNewGames(self):
        games = [{'Id': '1'}, {'Id': '2'}, {'Id': '3'}]
        result = main.GetNewGames(games, '2')
        self.assertEqual(result, [{'Id': '1'}])

    @patch('main.githubApi.get_gist')
    def test_GetLastId(self, mock_get_gist):
        mock_gist = MagicMock()
        mock_gist.description = '123'
        mock_get_gist.return_value = mock_gist

        result = main.GetLastId()
        self.assertEqual(result, '123')

    @patch('main.githubApi.get_gist')
    def test_SaveId(self, mock_get_gist):
        mock_gist = MagicMock()
        mock_get_gist.return_value = mock_gist

        main.SaveId('123')
        mock_gist.edit.assert_called_with('123')

    @patch('main.ConvertGameToEmbed', return_value={'title': 'Test Embed'})
    @patch('main.aiohttp.ClientSession')
    def test_Notify(self, mock_ClientSession, mock_ConvertGameToEmbed):
        game = {'Title': 'Test Game'}
        mock_session = MagicMock()
        mock_ClientSession.return_value.__aenter__.return_value = mock_session
        mock_session.post.return_value.__aenter__.return_value.status = 200

        asyncio.run(main.Notify(game))
        mock_ConvertGameToEmbed.assert_called_with(game)

    @patch('main.GetLastId', return_value='1')
    @patch('main.GetGames', return_value=[{'Id': '2'}])
    @patch('main.SaveId')
    @patch('main.Notify')
    def test_Start(self, mock_Notify, mock_SaveId, mock_GetGames, mock_GetLastId):
        main.Start()
        mock_GetLastId.assert_called_once()
        mock_GetGames.assert_called_once()
        mock_SaveId.assert_called_once_with('2')
        mock_Notify.assert_called_once()

if __name__ == '__main__':
    unittest.main()