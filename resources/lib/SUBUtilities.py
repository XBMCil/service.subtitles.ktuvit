# -*- coding: utf-8 -*-
import os
import re
import unicodedata
import json
import zlib
import shutil

import xbmc
import xbmcvfs
import xbmcaddon

try:
    # Python 3 - Kodi 19
    from urllib.request import Request, build_opener
    from urllib.parse import urlencode
except ImportError:
    # Python 2 - Kodi 18 and below
    from urllib2 import Request, build_opener
    from urllib import urlencode

__addon__ = xbmcaddon.Addon()
__version__ = __addon__.getAddonInfo('version')  # Module version
__scriptname__ = __addon__.getAddonInfo('name')
__language__ = __addon__.getLocalizedString
__profile__ = xbmc.translatePath(__addon__.getAddonInfo('profile'))
__temp__ = xbmc.translatePath(os.path.join(__profile__, 'temp', ''))
__kodi_version__ = xbmc.getInfoLabel('System.BuildVersion').split(' ')[0]

regexHelper = re.compile('\W+', re.UNICODE)

# ===============================================================================
# Private utility functions
# ===============================================================================
def normalizeString(_str):
    if not isinstance(_str, str):
        _str = unicodedata.normalize('NFKD', _str) #.encode('utf-8', 'ignore')
    return _str


def clean_title(item):
    title = os.path.splitext(os.path.basename(item["title"]))
    tvshow = os.path.splitext(os.path.basename(item["tvshow"]))

    if len(title) > 1:
        if re.match(r'^\.[a-z]{2,4}$', title[1], re.IGNORECASE):
            item["title"] = title[0]
        else:
            item["title"] = ''.join(title)
    else:
        item["title"] = title[0]

    if len(tvshow) > 1:
        if re.match(r'^\.[a-z]{2,4}$', tvshow[1], re.IGNORECASE):
            item["tvshow"] = tvshow[0]
        else:
            item["tvshow"] = ''.join(tvshow)
    else:
        item["tvshow"] = tvshow[0]

    # Removes country identifier at the end
    item['title'] = re.sub(r'\([^\)]+\)\W*$', '', item['title']).strip()
    item['tvshow'] = re.sub(r'\([^\)]+\)\W*$', '', item['tvshow']).strip()


def parse_rls_title(item):
    title = regexHelper.sub(' ', item["title"])
    tvshow = regexHelper.sub(' ', item["tvshow"])

    groups = re.findall(r"(.*?) (\d{4})? ?(?:s|season|)(\d{1,2})(?:e|episode|x|\n)(\d{1,2})", title, re.I)

    if len(groups) == 0:
        groups = re.findall(r"(.*?) (\d{4})? ?(?:s|season|)(\d{1,2})(?:e|episode|x|\n)(\d{1,2})", tvshow, re.I)

    if len(groups) > 0 and len(groups[0]) >= 3:
        title, year, season, episode = groups[0]
        item["year"] = str(int(year)) if len(year) == 4 else year

        item["tvshow"] = regexHelper.sub(' ', title).strip()
        item["season"] = str(int(season))
        item["episode"] = str(int(episode))
        log("TV Parsed Item: %s" % (item,))

    else:
        groups = re.findall(r"(.*?)(\d{4})", item["title"], re.I)
        if len(groups) > 0 and len(groups[0]) >= 1:
            title = groups[0][0]
            item["title"] = regexHelper.sub(' ', title).strip()
            item["year"] = groups[0][1] if len(groups[0]) == 2 else item["year"]

            log("MOVIE Parsed Item: %s" % (item,))


def log(msg):
    xbmc.log("### [%s] - %s" % (__scriptname__, msg), level=xbmc.LOGDEBUG)


def notify(msg_id):
    xbmc.executebuiltin((u'Notification(%s,%s)' % (__scriptname__, __language__(msg_id))).encode('utf-8'))


class SubsHelper:
    BASE_URL = "http://api.ktuvit.me/"

    def __init__(self):
        self.urlHandler = URLHandler()

    def get_subtitle_list(self, item):
        search_results = self._search(item)
        results = self._build_subtitle_list(search_results, item)

        return results

    # return list of movies / tv-series from the site`s search
    def _search(self, item):
        search_string = re.split(r'\s\(\w+\)$', item["tvshow"])[0] if item["tvshow"] else item["title"]
        log("search_string: %s" % search_string)

        query = {"SearchPhrase": search_string, "Version": "1.0"}
        if item["tvshow"]:
            query["SearchType"] = "FilmName"
            query["Season"] = item["season"]
            query["Episode"] = item["episode"]
            path = "FindSeries"
        else:
            query["SearchType"] = "FilmName"
            path = "FindFilm"
            if item["year"]:
                query["Year"] = item["year"]

        search_result = self.urlHandler.request(self.BASE_URL + path, data={"request": query})

        results = []

        if search_result is not None and search_result["IsSuccess"] is False:
            notify(32001)
            return results

        log("Results: %s" % search_result)

        if search_result is None or search_result["IsSuccess"] is False or len(search_result["Results"]) == 0:
            return results  # return empty set

        results += [{"name": search_string, "subs": {"he": search_result["Results"]}}]

        log("Subtitles: %s" % results)

        return results

    def _build_subtitle_list(self, search_results, item):
        ret = []
        for result in search_results:
            subs_list = result["subs"]

            if subs_list is not None:
                for language in subs_list.keys():
                    if xbmc.convertLanguage(language, xbmc.ISO_639_2) in item["3let_language"]:
                        for current in subs_list[language]:
                            title = current["SubtitleName"]
                            subtitle_rate = self._calc_rating(title, item["file_original_path"])

                            ret.append({'lang_index': item["3let_language"].index(
                                xbmc.convertLanguage(language, xbmc.ISO_639_2)),
                                'filename': title,
                                'language_name': xbmc.convertLanguage(language, xbmc.ENGLISH_NAME),
                                'language_flag': language,
                                'id': current["Identifier"],
                                'rating': '5',
                                'sync': subtitle_rate >= 3.8,
                                'hearing_imp': False,
                                'is_preferred': xbmc.convertLanguage(language, xbmc.ISO_639_2) == item[
                                    'preferredlanguage']
                            })

        return sorted(ret, key=lambda x: (x['is_preferred'], x['lang_index'], x['sync'], x['rating']), reverse=True)

    def _calc_rating(self, subsfile, file_original_path):
        file_name = os.path.basename(file_original_path)
        folder_name = os.path.split(os.path.dirname(file_original_path))[-1]

        subsfile = re.sub(r'\W+', '.', subsfile).lower()
        file_name = re.sub(r'\W+', '.', file_name).lower()
        folder_name = re.sub(r'\W+', '.', folder_name).lower()
        log("# Comparing Releases:\n [subtitle-rls] %s \n [filename-rls] %s \n [folder-rls] %s" % (
            subsfile, file_name, folder_name))

        subsfile = subsfile.split('.')
        file_name = file_name.split('.')[:-1]
        folder_name = folder_name.split('.')

        if len(file_name) > len(folder_name):
            diff_file = list(set(file_name) - set(subsfile))
            rating = (1 - (len(diff_file) / float(len(file_name)))) * 5
        else:
            diff_folder = list(set(folder_name) - set(subsfile))
            rating = (1 - (len(diff_folder) / float(len(folder_name)))) * 5

        log("\n rating: %f (by %s)" % (round(rating, 1), "file" if len(file_name) > len(folder_name) else "folder"))

        return round(rating, 1)

    def download(self, id, language, filename):
        ## Cleanup temp dir, we recomend you download/unzip your subs in temp folder and
        ## pass that to XBMC to copy and activate
        if xbmcvfs.exists(__temp__):
            shutil.rmtree(__temp__)
        xbmcvfs.mkdirs(__temp__)

        query = {"request": {"subtitleID": id}}

        f = self.urlHandler.request(self.BASE_URL + "Download", query)

        with open(filename, "wb") as subFile:
            subFile.write(f)
        subFile.close()


class URLHandler():
    def __init__(self):
        self.opener = build_opener()
        self.opener.addheaders = [('Accept-Encoding', 'gzip'),
                                  ('Accept-Language', 'en-us,en;q=0.5'),
                                  ('Pragma', 'no-cache'),
                                  ('Cache-Control', 'no-cache'),
                                  ('Content-type', 'application/json'),
                                  ('User-Agent',
                                   'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Kodi/%s Chrome/78.0.3904.97 Safari/537.36' % (
                                       __kodi_version__))]

    def request(self, url, data=None, query_string=None, referrer=None, cookie=None):
        if data is not None:
            data = json.dumps(data).encode('utf8')
        if query_string is not None:
            url += '?' + urlencode(query_string)
        if referrer is not None:
            self.opener.addheaders += [('Referrer', referrer)]
        if cookie is not None:
            self.opener.addheaders += [('Cookie', cookie)]

        content = None
        log("Getting url: %s" % (url))
        if data is not None:
            log("Post Data: %s" % (data))
        try:
            req = Request(url, data, headers={'Content-Type': 'application/json'})
            response = self.opener.open(req)
            content = None if response.code != 200 else response.read()

            if response.headers.get('content-encoding', '') == 'gzip':
                try:
                    content = zlib.decompress(content, 16 + zlib.MAX_WBITS)
                except zlib.error:
                    pass

            if response.headers.get('content-type', '').startswith('application/json'):
                content = json.loads(json.loads(content, encoding="utf-8"), encoding="utf-8")

            response.close()
        except Exception as e:
            log("Failed to get url: %s\n%s" % (url, e))
            # Second parameter is the filename
        return content
