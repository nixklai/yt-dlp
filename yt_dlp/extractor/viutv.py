from .common import InfoExtractor
from ..utils import traverse_obj
from urllib.request import Request
import json
from datetime import datetime
from random import choices


class ViuTVBaseIE(InfoExtractor):
    # _GEO_COUNTRIES = ['HK']

    _SUBTITLE_LOOKUP_DICT = {
        'Chinese': {
            'label': 'TRD',
            'text': 'Chinese',
            'locale': 'zh'
        },
        'English': {
            'label': 'GBR',
            'text': 'English',
            'locale': 'en'
        },
        'German': {
            'label': 'DEU',
            'text': 'German',
            'locale': 'de'
        },
        'Spanish': {
            'label': 'ESP',
            'text': 'Spanish',
            'locale': 'es'
        },
        'French': {
            'label': 'FRA',
            'text': 'French',
            'locale': 'fr'
        },
        'Italian': {
            'label': 'ITA',
            'text': 'Italian',
            'locale': 'it'
        },
        'Japanese': {
            'label': 'JAP',
            'text': 'Japanese',
            'locale': 'ja'
        }
    }

    def _fetch_program_api(self, program_slug):
        return self._download_json('https://api.viu.tv/production/programmes/%s' % program_slug, program_slug)

    def _generate_identifier(self):
        return ''.join(choices('1234567890abcdef', k=18))


class ViuTVProgramIE(ViuTVBaseIE):
    _VALID_URL = r'^https?://(?:www\.)?viu\.tv/encore/(?P<id>[a-z\-]+)$'
    IE_NAME = 'ViuTV:Programme'

    def _real_extract(self, url):
        program_slug = self._match_id(url)
        program_object = self._fetch_program_api(program_slug=program_slug)

        program_name = traverse_obj(program_object, ('programme', 'programmeMeta', 'seriesTitle'))
        episodes = traverse_obj(program_object, ('programme', 'episodes'))

        return {
            '_type': 'playlist',
            'id': program_slug,
            'title': program_name,
            'series_id': program_slug,
            'series': program_name,
            'entries': [{'_type': 'url', 'url': 'https://viu.tv/encore/%s/%s' % (program_slug, episode.get('slug'))} for episode in episodes]
        }


class ViuTVProductIE(ViuTVBaseIE):
    _VALID_URL = r'^https?://(?:www\.)?viu\.tv/(?:[\w\-/]+)#(?P<id>20[0-9]+)$'
    IE_NAME = 'ViuTV:Product'

    def _real_extract(self, url):
        product_id = self._match_id(url)
        identifier = self._generate_identifier()

        manifest_json = self._download_json('https://api.viu.now.com/p8/3/getVodURL', data=bytes(json.dumps({
            'callerReferenceNo': datetime.now().strftime('%Y%m%d%H%M%S'),
            'productId': product_id,
            'contentId': product_id,
            'contentType': 'Vod',
            'mode': 'prod',
            'PIN': 'password',
            'cookie': identifier,
            'deviceId': identifier,
            'deviceType': 'ANDROID_WEB',
            'format': 'HLS'
        }), encoding='utf-8'), video_id=product_id)

        if manifest_json.get('responseCode') != 'SUCCESS':
            self.report_warning(f'Product not found', video_id=product_id)
            return

        manifest_url = traverse_obj(manifest_json, ('asset', 0))
        
    
        subtitles = {}
        for (_, language) in enumerate(self._SUBTITLE_LOOKUP_DICT):
            
            subtitles[traverse_obj(self._SUBTITLE_LOOKUP_DICT, (language, 'locale'))] = [{
                'url': 'https://static.viu.tv/subtitle/%s/%s-%s.srt' % (product_id, product_id, self._SUBTITLE_LOOKUP_DICT[language]['label'])
            }]

        return {
            'id': product_id,
            'title': product_id,
            'formats': self._extract_mpd_formats(manifest_url, video_id=product_id),
            'subtitles': subtitles
        }


class ViuTVEpisodeIE(ViuTVBaseIE):
    _VALID_URL = r'^https?://(?:www\.)?viu\.tv/encore/(?P<program_id>[a-z\-]+)/(?P<id>[a-z0-9\-]+)$'
    IE_NAME = 'ViuTV:Episode'

    def _real_extract(self, url):
        identifier = self._generate_identifier()
        episode_slug = self._match_id(url)
        program_slug = self._search_regex(self._VALID_URL, url, 'program_id', group='program_id')

        programme = self._fetch_program_api(program_slug=program_slug)
        episode = [episode for episode in traverse_obj(programme, ('programme', 'episodes')) if episode.get('slug') == episode_slug][0]
        _product_id = episode.get('productId')

        manifest_request_data = bytes(json.dumps({
            'callerReferenceNo': datetime.now().strftime('%Y%m%d%H%M%S'),
            'productId': _product_id,
            'contentId': _product_id,
            'contentType': 'Vod',
            'mode': 'prod',
            'PIN': 'password',
            'cookie': identifier,
            'deviceId': identifier,
            'deviceType': 'ANDROID_WEB',
            'format': 'HLS'
        }), encoding='utf-8')

        manifest_json = self._download_json('https://api.viu.now.com/p8/3/getVodURL', data=manifest_request_data, video_id=episode_slug)
        manifest_url = traverse_obj(manifest_json, ('asset', 0))
        subtitles = {}
        
        for language in episode.get('productSubtitle').split(','):
            key = traverse_obj(self._SUBTITLE_LOOKUP_DICT, (language, 'locale'))
            
            subtitles[key] = [{
                'url': 'https://static.viu.tv/subtitle/%s/%s-%s.srt' % (_product_id, _product_id, traverse_obj(self._SUBTITLE_LOOKUP_DICT, (language, 'label')))
            }]

        return {
            'id': episode_slug,
            'title': episode.get('episodeNameU3'),
            'series': traverse_obj(episode, ('programmeMeta', 'seriesTitle')),
            'series_id': traverse_obj(programme, ('programme', 'slug')),
            'season_number': int(traverse_obj(episode, ('programmeMeta', 'seasonNo'))),
            'episode': episode.get('episodeNameU3'),
            'episode_number': episode.get('episodeNum'),
            'formats': self._extract_mpd_formats(manifest_url, video_id=episode_slug),
            'subtitles': subtitles
        }
