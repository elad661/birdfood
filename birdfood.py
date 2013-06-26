#! /bin/env python
# coding=utf8
#
# birdfood - A web service to generate Atom Feeds for twitter accounts or searches
#
#╔════════════════════════════════════════════════════════════════════════════╗
#║ Copyright © 2013, Elad Alfassa <elad@fedoraproject.org>                    ║
#║                                                                            ║
#║   This program is free software: you can redistribute it and/or modify     ║
#║   it under the terms of the GNU General Public License as published by     ║
#║   the Free Software Foundation, either version 3 of the License, or        ║
#║   (at your option) any later version.                                      ║
#║                                                                            ║
#║   This program is distributed in the hope that it will be useful,          ║
#║   but WITHOUT ANY WARRANTY; without even the implied warranty of           ║
#║   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            ║
#║   GNU General Public License for more details.                             ║
#║                                                                            ║
#║   You should have received a copy of the GNU General Public License        ║
#║   along with this program.  If not, see <http://www.gnu.org/licenses/>.    ║
#║                                                                            ║
#╚════════════════════════════════════════════════════════════════════════════╝
from __future__ import print_function
import tweepy
import cherrypy
from cherrypy.process.plugins import Daemonizer
import ConfigParser
import os
import os.path
import sys
import re
import optparse
from datetime import datetime
from mako.template import Template
from mako import exceptions
from urllib2 import quote

class Feeder():
    """Main app class, everything happens here"""

    def __init__(self, consumer_key, consumer_secret, token, token_secret):
        self.auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        self.auth.set_access_token(token, token_secret)
        self.api = tweepy.API(self.auth)

    def make_atom(self, timeline, user):
        """Make an atom feed from template"""
        try:
            template = Template(filename='feed_template.xml', 
                                input_encoding='utf-8', 
                                default_filters=['decode.utf8'])

            return template.render(now = datetime.now().isoformat(),
                               self_id = cherrypy.url(),
                               url = 'https://twitter.com/%s/' % user,
                               feed_name = user,
                               feed_entries = timeline)
        except:
            print(exceptions.text_error_template().render())
            return exceptions.html_error_template().render()

    @cherrypy.expose()
    def user(self, account_name):
        """ User feed """
        feed_arr = []
        for tweet in tweepy.Cursor(self.api.user_timeline, id=account_name, count=75).items(75):
            tweet.link = 'https://twitter.com/%s/status/%s' % (tweet.user.screen_name, tweet.id_str)
            tweet.created_at = tweet.created_at.isoformat()
            feed_arr.append(tweet)
        
        return self.make_atom(feed_arr, account_name)

    @cherrypy.expose()
    def search(self, string):
        """ Search feed """
        feed_arr = []
        for tweet in tweepy.Cursor(self.api.search, q=string, result_type='recent', count=75).items(75):
            tweet.link = 'https://twitter.com/%s/status/%s' % (quote(tweet.user.screen_name), tweet.id_str)
            tweet.created_at = tweet.created_at.isoformat()
            feed_arr.append(tweet)
        
        return self.make_atom(feed_arr, string)

    @cherrypy.expose()
    def index(self):
        return "You're probably in the wrong place, mate"

def main(argv=None):
    config_file = 'birdfood.conf'
    parser = optparse.OptionParser('%prog [options]')
    parser.add_option('-c', '--config',
            help = 'Specify path to configuration file')
    parser.add_option('-p', '--port', 
            help = 'Specify port number to listen on (default is 8080')
    parser.add_option('-d', '--deamonize', action="store_true", dest="deamon",
            help='Run as a deamon')
    opts, args = parser.parse_args(argv)
    if opts.config and os.path.isfile(opts.config):
        config_file = opts.config
    elif not os.path.isfile(config_file):
        print("Can't find configuration file %s" % config_file)
        return 1
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    if (not config.has_section('birdfood') or not config.has_option('birdfood', 'consumer_key')
      or not config.has_option('birdfood', 'consumer_secret')):
        print("Config file malformed")
        return 2

    consumer_key = config.get('birdfood', 'consumer_key')
    consumer_secret = config.get('birdfood', 'consumer_secret')

    if not config.has_option('birdfood','token') or not config.has_option('birdfood','token_secret'):
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        print("Please authenticate with twitter using this link: %s" % auth.get_authorization_url())

        code = raw_input('Enter authentication code from twitter: ').strip()
        token = auth.get_access_token(verifier=code)

        config.set('birdfood', 'token', token.key)
        config.set('birdfood', 'token_secret', token.secret)
        config_file_object = open(config_file, 'w')
        config.write(config_file_object)
        config_file_object.close()
    if opts.port and not opts.port.isdigit():
        print("Invalid port number!")
        return 3
    elif opts.port:
        cherrypy.config.update({'server.socket_port': int(opts.port)})
    token = config.get('birdfood','token')
    token_secret = config.get('birdfood','token_secret')
    if (opts.deamon):
        logfile = os.path.join(os.getcwd(), 'birdfood.log')
        d = Daemonizer(cherrypy.engine, stdout=logfile, stderr=logfile)
        d.subscribe()
    cherrypy.quickstart(Feeder(consumer_key, consumer_secret, token, token_secret))

if __name__ == '__main__':
    main()
