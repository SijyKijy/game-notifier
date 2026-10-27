import unittest
from unittest.mock import patch, MagicMock
import main
import asyncio
import os
import subprocess
import sys

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
        self.assertEqual(result, '')

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

    @patch('main.browser_requests.get')
    def test_GetPage(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b'<html></html>'

        result = main.GetPage()
        self.assertEqual(result, b'<html></html>')
        mock_get.assert_called_once_with(
            'https://freetp.org/po-seti/', impersonate='chrome', timeout=30
        )

        for status in (403, 500):
            with self.subTest(status=status):
                mock_get.return_value.status_code = status
                with self.assertRaisesRegex(Exception, f'Invalid response status: {status}'):
                    main.GetPage()

        mock_get.side_effect = TimeoutError('Request timed out')
        with self.assertRaisesRegex(Exception, 'Error when getting page: Request timed out'):
            main.GetPage()

    def test_ConvertPageToGame(self):
        page = main.BeautifulSoup('''
            <article class="game-card fixed_story">
                <a class="game-card__media-link" href="https://freetp.org/po-seti/2266-conan.html">
                    <div class="game-card__media">
                        <img src="/uploads/posts/conan.jpg">
                        <div class="game-card__update"><span>12-06-2026</span><b>Обновлено</b></div>
                    </div>
                </a>
                <h2 class="game-card__title"><a href="https://freetp.org/po-seti/2266-conan.html">Conan Exiles</a></h2>
                <div class="text game-card__excerpt">
                    <p><!--dle_image_begin:image--><img src="/image.jpg"><!--dle_image_end-->Conan — игра &amp; приключение.</p>
                    <p>Ещё один абзац.</p>
                    <p><br><strong>Способ по которому можно поиграть:</strong> Steam.</p>
                </div>
            </article>
        ''', 'html.parser')
        game = page.select_one('article')
        self.assertEqual(main.ConvertPageToGame(game), {
            'Id': '2266',
            'Title': 'Conan Exiles',
            'Url': 'https://freetp.org/po-seti/2266-conan.html',
            'PhotoUrl': 'https://freetp.org/uploads/posts/conan.jpg',
            'Comment': 'Обновлено',
            'Description': 'Conan — игра & приключение. Ещё один абзац.',
        })

        game.select_one('.game-card__media').decompose()
        result = main.ConvertPageToGame(game)
        self.assertIsNone(result['PhotoUrl'])
        self.assertIsNone(result['Comment'])
        game.select_one('.game-card__excerpt').decompose()
        self.assertEqual(main.ConvertPageToGame(game)['Description'], '')

        game.select_one('.game-card__title a')['href'] = 'https://freetp.org/po-seti/'
        self.assertIsNone(main.ConvertPageToGame(game))
        game.select_one('.game-card__title').decompose()
        self.assertIsNone(main.ConvertPageToGame(game))

    @patch('main.GetClaudeDescription')
    @patch('main.GetPerpDescription')
    @patch('main.get_steam_context')
    def test_description_without_ai(self, mock_steam, mock_perp, mock_claude):
        game = {
            'Title': 'CRACK', 'Url': 'https://freetp.org/po-seti/7367-crack.html',
            'PhotoUrl': None, 'Comment': None,
            'Description': 'CRACK — кооперативное приключение для 1–4 игроков.',
        }
        for provider in ('perplexity', '', 'claude', 'none'):
            with self.subTest(provider=provider), patch.dict(os.environ, {
                'DESC_PROVIDER': provider, 'CLAUDE_CODE_OAUTH_TOKEN': '',
            }), patch('main.PERP_TOKEN', ''):
                embed = main.ConvertGameToEmbed(game)
                self.assertEqual(embed['description'], game['Description'])
        mock_perp.assert_not_called()
        mock_claude.assert_not_called()
        mock_steam.assert_not_called()

    @patch.dict(os.environ, {'DESC_PROVIDER': 'none'})
    @patch('main.GetDescription', return_value='')
    def test_description_last_resort(self, mock_description):
        game = {
            'Title': 'CRACK', 'Url': 'https://freetp.org/po-seti/7367-crack.html',
            'PhotoUrl': None, 'Comment': None,
        }
        self.assertEqual(main.ConvertGameToEmbed(game)['description'], r"¯\_(ツ)_/¯")
        for description in ('', None):
            with self.subTest(description=description):
                game['Description'] = description
                self.assertEqual(main.ConvertGameToEmbed(game)['description'], r"¯\_(ツ)_/¯")

    @patch.dict(os.environ, {'DESC_PROVIDER': 'perplexity'})
    @patch('main.PERP_TOKEN', 'test-token')
    @patch('main.PERP_MODEL', 'test-model')
    @patch('main.PERP_PROMPT', 'test-prompt')
    @patch('main.PERP_URL', 'https://example.invalid/chat')
    @patch('main.requests.post')
    def test_description_falls_back_on_ai_error(self, mock_post):
        game = {
            'Title': 'CRACK', 'Url': 'https://freetp.org/po-seti/7367-crack.html',
            'PhotoUrl': None, 'Comment': 'Обновлено', 'Description': 'Описание FreeTP',
        }
        mock_post.return_value.status_code = 500
        self.assertEqual(main.ConvertGameToEmbed(game)['description'], 'Обновлено\n---\nОписание FreeTP')
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'choices': [{'message': {'content': 'Описание AI'}}]}
        self.assertEqual(main.ConvertGameToEmbed(game)['description'], 'Обновлено\n---\nОписание AI')

    @patch.dict(os.environ, {'DESC_PROVIDER': 'claude', 'CLAUDE_CODE_OAUTH_TOKEN': 'test-token'})
    @patch('main.get_steam_context', return_value=None)
    @patch('main.subprocess.run')
    def test_description_falls_back_on_claude_error(self, mock_run, mock_steam):
        game = {
            'Title': 'CRACK', 'Url': 'https://freetp.org/po-seti/7367-crack.html',
            'PhotoUrl': None, 'Comment': None, 'Description': 'Описание FreeTP',
        }
        mock_run.return_value.returncode = 1
        self.assertEqual(main.ConvertGameToEmbed(game)['description'], 'Описание FreeTP')
        mock_run.return_value.returncode = 0
        for output in ('', ' \n\t'):
            with self.subTest(output=output):
                mock_run.return_value.stdout = output
                self.assertEqual(main.ConvertGameToEmbed(game)['description'], 'Описание FreeTP')
        mock_run.return_value.stdout = 'Описание Claude'
        self.assertEqual(main.ConvertGameToEmbed(game)['description'], 'Описание Claude')
        for error in (subprocess.TimeoutExpired('claude', 180), FileNotFoundError('claude')):
            with self.subTest(error=type(error).__name__):
                mock_run.side_effect = error
                self.assertEqual(main.ConvertGameToEmbed(game)['description'], 'Описание FreeTP')
                self.assertEqual(mock_run.call_args.kwargs['timeout'], 180)

    def test_import_without_ai_settings(self):
        env = os.environ.copy()
        for name in ('PERP_TOKEN', 'PERP_MODEL', 'PERP_PROMPT', 'PERP_URL', 'CLAUDE_CODE_OAUTH_TOKEN'):
            env.pop(name, None)
        env.update({
            'GIST_ID': 'test', 'GH_TOKEN': 'test-token', 'WEBHOOKS_PATH': '[]',
            'DESC_PROVIDER': 'none', 'PYTHON_DOTENV_DISABLED': '1',
        })
        result = subprocess.run(
            [sys.executable, '-B', '-W', 'error', '-c', "import main; assert main.GetDescription('CRACK') == ''"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @patch('main.GetPage')
    @patch('main.BeautifulSoup')
    def test_GetGames(self, mock_soup, mock_GetPage):
        mock_GetPage.return_value = b'<html></html>'
        mock_element = MagicMock()
        mock_soup.return_value.select.return_value = [mock_element]

        with patch('main.ConvertPageToGame', return_value={'Id': '1'}):
            result = main.GetGames()
            self.assertEqual(result, [{'Id': '1'}])
            mock_soup.return_value.select.assert_called_once_with('article.game-card')

    @patch('main.GetPage', return_value=b'<html>Access denied</html>')
    def test_GetGames_rejects_unexpected_markup(self, mock_GetPage):
        with self.assertRaisesRegex(ValueError, 'Game cards not found'):
            main.GetGames()

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
    @patch('asyncio.run', side_effect=lambda coroutine: coroutine.close())
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
