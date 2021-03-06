# -*- coding:utf-8 -*-
import base64
import binascii
import json
import os
import requests
from Crypto.Cipher import AES


class Encrypyed():
    def __init__(self):
        self.modulus = '00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e4' \
                       '17629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575' \
                       'cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7'
        self.nonce = '0CoJUm6Qyw8W8jud'
        self.pub_key = '010001'

    # 登录加密算法, 基于https://github.com/stkevintan/nw_musicbox脚本实现
    def encrypted_request(self, text):
        text = json.dumps(text)
        sec_key = self.create_secret_key(8)
        enc_text = self.aes_encrypt(self.aes_encrypt(text, self.nonce), sec_key.decode('utf-8'))
        enc_sec_key = self.rsa_encrypt(sec_key, self.pub_key, self.modulus)
        data = {'params': enc_text, 'encSecKey': enc_sec_key}
        return data

    def aes_encrypt(self, text, sec_key):
        pad = 16 - len(text) % 16
        text = text + chr(pad) * pad
        encryptor = AES.new(sec_key.encode('utf-8'), AES.MODE_CBC, b'0102030405060708')
        ciphertext = encryptor.encrypt(text.encode('utf-8'))
        # b64encode函数的参数为byte类型，所以必须先转码
        ciphertext = base64.b64encode(ciphertext).decode('utf-8')
        return ciphertext

    def rsa_encrypt(self, text, pub_key, modulus):
        text = text[::-1]
        rs = pow(int(binascii.hexlify(text), 16), int(pub_key, 16), int(modulus, 16))
        # format(rs, 'x')  decimal to hexdecimal
        # Python zfill() 方法返回指定长度的字符串，原字符串右对齐，前面填充0。
        return format(rs, 'x').zfill(256)

    def create_secret_key(self, size):
        # 作用是返回的二进制数据的十六进制表示。每一个字节的数据转换成相应的2位十六进制表示
        return binascii.hexlify(os.urandom(size))


class Song():
    """
    歌曲对象，用于存储歌曲的信息
    """

    def __init__(self, song_id, song_name, song_num, song_url=None):
        self.song_id = song_id
        self.song_name = song_name
        self.song_num = song_num
        self.song_url = '' if song_url is None else song_url


class Crawler():
    """
    网易云爬取API
    """

    def __init__(self, timeout=60, cookie_path='.'):
        self.headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'music.163.com',
            'Referer': 'http://music.163.com/search/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.download_session = requests.Session()
        self.timeout = timeout
        self.ep = Encrypyed()

    def post_request(self, url, params):
        """
        Post请求
        :return: 字典
        """

        data = self.ep.encrypted_request(params)
        resp = self.session.post(url, data=data, timeout=self.timeout)
        result = resp.json()
        if result['code'] != 200:
            print('post_request error', result['code'])
        else:
            return result

    def search(self, search_content, search_type, limit=9):
        """
        搜索API
        :params search_content: 搜索内容
        :params search_type: 搜索类型
        :params limit: 返回结果数量
        :return: 字典.
        """

        url = 'http://music.163.com/weapi/cloudsearch/get/web?csrf_token='
        params = {'s': search_content, 'type': search_type, 'offset': 0, 'sub': 'false', 'limit': limit}
        result = self.post_request(url, params)

        return result

    def download_song(self, song_name, song_num, quiet=True, limit=9):
        """
        根据音乐名搜索
        :params song_name: 音乐名
        :params song_num: 下载的歌曲数
        :params quiet: 自动选择匹配最优结果
        :params limit: 返回结果数量
        :return: Song独享
        """

        result = self.search(song_name, search_type=1, limit=limit)
        if result['result']['songCount'] <= 0:
            print('Song {} not existed.'.format(song_name))
        else:
            songs = result['result']['songs']
            if quiet:
                song_id, song_name = songs[0]['id'], songs[0]['name']
                song = Song(song_id=song_id, song_name=song_name, song_num=song_num)
                return song

    def get_song_url(self, song_id, bit_rate=320000):
        """
        获得歌曲的下载地址
        :params song_id: 音乐ID<int>.
        :params bit_rate: {'MD 128k': 128000, 'HD 320k': 320000}
        :return: 歌曲下载地址
        """

        url = 'http://music.163.com/weapi/song/enhance/player/url?csrf_token='
        csrf = ''
        params = {'ids': [song_id], 'br': bit_rate, 'csrf_token': csrf}
        result = self.post_request(url, params)
        # 歌曲下载地址
        song_url = result['data'][0]['url']

        # 歌曲不存在
        if song_url is None:
            print('Song {} is not available due to copyright issue.'.format(song_id))
        else:
            return song_url

    def get_song_by_url(self, song_url, song_name, song_num, folder):
        """
        下载歌曲到本地
        :params song_url: 歌曲下载地址
        :params song_name: 歌曲名字
        :params song_num: 下载的歌曲数
        :params folder: 保存路径
        """
        if not os.path.exists(folder):
            os.makedirs(folder)
        fpath = os.path.join(folder, str(song_num) + '_' + (''.join(song_name.split())) + '.mp3')
        print(fpath)

        if not os.path.exists(fpath):
            response = self.download_session.get(song_url, timeout=self.timeout, stream=True)
            chunk_size = 1024  # 每次下载的数据大小
            content_size = int(response.headers['content-length'])  # 总大小
            print('[文件大小]:%0.2f KB' % (content_size / chunk_size))  # 换算单位
            with open(fpath, 'wb') as f:
                for data in response.iter_content(chunk_size=chunk_size):
                    f.write(data)


class Netease():
    """
    网易云音乐下载
    """

    def __init__(self, timeout, folder, quiet, cookie_path):
        self.crawler = Crawler(timeout, cookie_path)
        self.folder = '.' if folder is None else folder
        self.quiet = quiet

    def download_song(self, song_name, song_num):
        """
        根据歌曲名进行搜索
        :params song_name: 歌曲名字
        :params song_num: 下载的歌曲数
        """

        try:
            song = self.crawler.download_song(song_name, song_num, self.quiet)
        except:
            print('download_song_by_serach error')
            return
        # 如果找到了音乐, 则下载
        if song is not None:
            print(f'{song.song_name}id: {song.song_id}')
            self._download_song(song.song_id, song.song_name, song.song_num, self.folder)

    def _download_song(self, song_id, song_name, song_num, folder='.'):
        """
        通过歌曲的ID下载
        :params song_id: 歌曲ID
        :params song_name: 歌曲名
        :params song_num: 下载的歌曲数
        :params folder: 保存地址
        """
        try:
            url = self.crawler.get_song_url(song_id)
            # 去掉非法字符
            song_name = song_name.replace('/', '')
            song_name = song_name.replace('.', '')
            self.crawler.get_song_by_url(url, song_name, song_num, folder)
            print(f'{song_name} downloaded successfully')
        except:
            print('download_song error')


if __name__ == '__main__':
    timeout = 60
    output = 'Musics'
    quiet = True
    cookie_path = 'Cookie'
    netease = Netease(timeout, output, quiet, cookie_path)
    netease.download_song('way back home', 1)
