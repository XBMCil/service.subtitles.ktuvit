# -*- coding: utf-8 -*-
import test_helpers
from unittest import TestCase
from resources.lib.SUBUtilities import SubsHelper, parse_rls_title


class TestSUBUtilities(TestCase):
    def setUp(self):
        self.helper = SubsHelper()

    def test_get_subtitle_list(self):
        item = {'episode': '1', 'title': 'The Blood of Man', 'season': '2', 'year': '', 'tvshow': "Da Vinci's Demons",
                '3let_language': ['eng', 'heb']}

        result = self.helper._search(item)
        self.assertEqual(result[0]['name'], item["tvshow"])
        self.assertGreater(len(result[0]['subs']['he']), 0)

    def test_get_subtitle_list2(self):
        item = {'episode': '', 'title': 'Two.and.a.Half.Men.S11E13.480p.HDTV.X264-DIMENSION',
                'season': '', 'year': '', 'tvshow': '', '3let_language': ['en', 'he']}

        parse_rls_title(item)
        result = self.helper._search(item)
        self.assertEqual(result[0]['name'], 'Two and a Half Men')
        self.assertGreater(len(result[0]['subs']['he']), 0)

    def test_get_subtitle_list3(self):
        item = {'episode': '', 'title': 'Inception', 'season': '', 'year': '2010',
                'tvshow': '', '3let_language': ['en', 'he']}

        result = self.helper._search(item)
        self.assertEqual(result[0]['name'], item['title'])
        self.assertGreater(len(result[0]['subs']['he']), 0)

    def test_get_subtitle_list4(self):
        item = {'episode': '', 'title': 'The.Flash.2014.S02E05.480p.HDTV.X264-DIMENSION.mkv',
                'preferredlanguage': 'heb', 'season': '', 'year': '', 'tvshow': '', '3let_language': ['heb']}

        parse_rls_title(item)
        result = self.helper._search(item)
        self.assertEqual(result[0]['name'], 'The Flash')
        self.assertGreater(len(result[0]['subs']['he']), 0)

    def test_get_subtitle_list5_should_ignore_year_on_tvshow(self):
        item = {'episode': '5', 'title': 'Episode 5', 'preferredlanguage': '', 'season': '3',
                'year': '2016', 'tvshow': 'The Affair', '3let_language': ['eng', 'heb']}

        parse_rls_title(item)
        result = self.helper._search(item)

        self.assertEqual(result[0]['name'], item["tvshow"])
        self.assertGreater(len(result[0]['subs']['he']), 0)
