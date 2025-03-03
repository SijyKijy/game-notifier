import unittest
from unittest.mock import patch, MagicMock
import main
import asyncio

class TestMain(unittest.TestCase):
    @patch('main.requests.post')
    def test_GetPerpDescription(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': 'Test Description'}}]
        }
        result = main.GetPerpDescription('Test Game')
        self.assertEqual(result, 'Test Description')

        mock_post.return_value.status_code = 500
        mock_post.return_value.json.return_value = {}
        result = main.GetPerpDescription('Test Game')
        self.assertEqual(result, "¯\_(ツ)_/¯")

    @patch('main.requests.post')
    def test_GetPerpDescription_with_think_block(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'choices': [{
                'message': {
                    'content': '<think>Some reasoning</think>\nActual Description without think block.'
                }
            }]
        }
        result = main.GetPerpDescription('Test Game with Think')
        self.assertEqual(result, 'Actual Description without think block.')

    @patch('main.requests.post')
    def test_GetPage(self, mock_post):
        mock_post.return_value.json.return_value = {
            "status": "ok",
            "solution": {
                "response": "<html></html>"
            }
        }

        result = main.GetPage()
        self.assertEqual(result, b'<html></html>')

        mock_post.return_value.json.return_value = {
            "status": "error",
            "message": "Cloudflare challenge failed"
        }
        
        with self.assertRaises(Exception) as context:
            main.GetPage()
        self.assertTrue('Failed to bypass Cloudflare protection' in str(context.exception))

    @patch('main.GetPage')
    @patch('main.BeautifulSoup')
    def test_GetGames(self, mock_soup, mock_GetPage):
        mock_GetPage.return_value = b'<html></html>'
        mock_element = MagicMock()
        mock_soup.return_value.select.return_value = [mock_element]

        with patch('main.ConvertPageToGame', return_value={'Id': '1'}):
            result = main.GetGames()
            self.assertEqual(result, [{'Id': '1'}])

    def test_GetNewGames_first_id_changed(self):
        games = [{'Id': '1'}, {'Id': '2'}, {'Id': '3'}]
        # Случай 1: Изменился первый ID
        result = main.GetNewGames(games, '2')
        self.assertEqual(result, [{'Id': '1'}])

    def test_GetNewGames_second_id_changed(self):
        games = [{'Id': '1'}, {'Id': '2'}, {'Id': '3'}]
        # Случай 2: Первый ID не изменился, но изменился второй ID
        result = main.GetNewGames(games, '1,3')
        self.assertEqual(result, [{'Id': '2'}])

    def test_GetNewGames_both_ids_changed(self):
        games = [{'Id': '1'}, {'Id': '2'}, {'Id': '3'}]
        # Случай 3: Оба ID изменились
        result = main.GetNewGames(games, '4,5')
        self.assertEqual(result, games)

    def test_GetNewGames_no_changes(self):
        games = [{'Id': '1'}, {'Id': '2'}, {'Id': '3'}]
        # Случай 4: Ни один ID не изменился
        result = main.GetNewGames(games, '1,2')
        self.assertEqual(result, [])

    @patch('main.githubApi.get_gist')
    def test_GetLastId(self, mock_get_gist):
        mock_gist = MagicMock()
        mock_gist.description = '123,456'
        mock_get_gist.return_value = mock_gist

        result = main.GetLastId()
        self.assertEqual(result, '123,456')

    @patch('main.githubApi.get_gist')
    def test_SaveId(self, mock_get_gist):
        mock_gist = MagicMock()
        mock_get_gist.return_value = mock_gist

        main.SaveId('123,456')
        mock_gist.edit.assert_called_with('123,456')

        # Проверка обработки ошибок
        mock_gist.edit.side_effect = Exception('Test error')
        main.SaveId('123,456')  # Ошибка должна быть обработана внутри метода

    @patch('main.ConvertGameToEmbed', return_value={'title': 'Test Embed'})
    @patch('main.aiohttp.ClientSession')
    def test_Notify(self, mock_ClientSession, mock_ConvertGameToEmbed):
        game = {'Title': 'Test Game'}
        mock_session = MagicMock()
        mock_ClientSession.return_value.__aenter__.return_value = mock_session
        mock_session.post.return_value.__aenter__.return_value.status = 200

        asyncio.run(main.Notify(game))
        mock_ConvertGameToEmbed.assert_called_with(game)

    @patch('main.GetLastId', return_value='1,2')
    @patch('main.GetGames', return_value=[{'Id': '3'}, {'Id': '4'}])
    @patch('main.GetNewGames', return_value=[{'Id': '3'}, {'Id': '4'}])
    @patch('main.SaveId')
    @patch('asyncio.run')
    def test_Start(self, mock_asyncio_run, mock_SaveId, mock_GetNewGames, mock_GetGames, mock_GetLastId):
        main.Start()
        mock_GetLastId.assert_called_once()
        mock_GetGames.assert_called_once()
        mock_GetNewGames.assert_called_once()
        mock_SaveId.assert_called_once_with('3,4')
        
    @patch('main.GetLastId', return_value='1,2')
    @patch('main.GetGames', return_value=[{'Id': '1'}, {'Id': '2'}])
    @patch('main.SaveId')
    @patch('asyncio.run')
    def test_Start_no_new_games(self, mock_asyncio_run, mock_SaveId, mock_GetGames, mock_GetLastId):
        main.Start()
        mock_GetLastId.assert_called_once()
        mock_GetGames.assert_called_once()
        mock_SaveId.assert_not_called()
        mock_asyncio_run.assert_not_called()
        
    @patch('main.GetLastId', return_value='1,2')
    @patch('main.GetGames', return_value=[])
    @patch('main.SaveId')
    @patch('asyncio.run')
    def test_Start_no_games(self, mock_asyncio_run, mock_SaveId, mock_GetGames, mock_GetLastId):
        main.Start()
        mock_GetLastId.assert_called_once()
        mock_GetGames.assert_called_once()
        mock_SaveId.assert_not_called()
        mock_asyncio_run.assert_not_called()

if __name__ == '__main__':
    unittest.main()