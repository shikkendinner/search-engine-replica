
# Copyright (C) 2011 by Peter Goodman
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import urllib2
import urlparse
from BeautifulSoup import *
from collections import defaultdict
import re
import redis
import pickle
from pagerank import page_rank

def attr(elem, attr):
    """An html attribute from an html element. E.g. <a href="">, then
    attr(elem, "href") will get the href or an empty string."""
    try:
        return elem[attr]
    except:
        return ""

WORD_SEPARATORS = re.compile(r'\s|\n|\r|\t|[^a-zA-Z0-9\-_]')


def setup_database():
    r_server = redis.Redis('localhost')

    r_server.delete("page_rank_dict")
    r_server.delete("Document_index_dict")
    r_server.delete("wordTodoc")
    r_server.delete("Document_index_title")

    return r_server


def add_to_list(r_server, list_name, word):
    r_server.rpush(list_name, word)


def add_to_set(r_server, set_name, value):
    r_server.sadd(set_name, value)


class crawler(object):
    """Represents 'Googlebot'. Populates a database by crawling and indexing
    a subset of the Internet.

    This crawler keeps track of font sizes and makes it simpler to manage word
    ids and document ids."""

    def __init__(self, db_conn, url_file = "urls.txt", spec_url = "0"):
        """Initialize the crawler with a connection to the database to populate
        and with the file containing the list of seed URLs to begin indexing."""

        # _url_queue is a list of tuples of all the urls extracted from the txt document
        #  and their depth to the starting url.
        self._url_queue = []
        # _doc_id_cache uses the url as the key, and the doc_id as the value.
        self._doc_id_cache = {}
        # _word_id_cache uses the word as the key, and the word_id as the value.
        self._word_id_cache = {}

        # _inverted_index_dict uses the word_id as the key and set of doc_id as the value
        self._inverted_index_dict = {}

        # _resolved_inverted_index_dict uses the word as the key and set of urls as the value
        self._resolved_inverted_index_dict = {}

        # _document_index contains information about each document
        self._document_index = []

        # _word_lexicon contains a list of words
        self._word_lexicon = []

        # redis database
        self.redis_server = setup_database()

        # list for the links between websites
        self._links_list = []

        # list of page ranks
        self._page_rank_list = {}

        # functions to call when entering and exiting specific tags
        self._enter = defaultdict(lambda *a, **ka: self._visit_ignore)
        self._exit = defaultdict(lambda *a, **ka: self._visit_ignore)

        # add a link to our graph, and indexing info to the related page
        self._enter['a'] = self._visit_a

        # record the currently indexed document's title an increase
        # the font size
        def visit_title(*args, **kargs):
            self._visit_title(*args, **kargs)
            self._increase_font_factor(7)(*args, **kargs)

        # increase the font size when we enter these tags
        self._enter['b'] = self._increase_font_factor(2)
        self._enter['strong'] = self._increase_font_factor(2)
        self._enter['i'] = self._increase_font_factor(1)
        self._enter['em'] = self._increase_font_factor(1)
        self._enter['h1'] = self._increase_font_factor(7)
        self._enter['h2'] = self._increase_font_factor(6)
        self._enter['h3'] = self._increase_font_factor(5)
        self._enter['h4'] = self._increase_font_factor(4)
        self._enter['h5'] = self._increase_font_factor(3)
        self._enter['title'] = visit_title

        # decrease the font size when we exit these tags
        self._exit['b'] = self._increase_font_factor(-2)
        self._exit['strong'] = self._increase_font_factor(-2)
        self._exit['i'] = self._increase_font_factor(-1)
        self._exit['em'] = self._increase_font_factor(-1)
        self._exit['h1'] = self._increase_font_factor(-7)
        self._exit['h2'] = self._increase_font_factor(-6)
        self._exit['h3'] = self._increase_font_factor(-5)
        self._exit['h4'] = self._increase_font_factor(-4)
        self._exit['h5'] = self._increase_font_factor(-3)
        self._exit['title'] = self._increase_font_factor(-7)

        # never go in and parse these tags
        self._ignored_tags = set([
            'meta', 'script', 'link', 'meta', 'embed', 'iframe', 'frame',
            'noscript', 'object', 'svg', 'canvas', 'applet', 'frameset',
            'textarea', 'style', 'area', 'map', 'base', 'basefont', 'param',
        ])

        # set of words to ignore
        self._ignored_words = set([
            '', 'the', 'of', 'at', 'on', 'in', 'is', 'it',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
            'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
            'u', 'v', 'w', 'x', 'y', 'z', 'and', 'or',
        ])

        # initialize the doc_id and word_id
        self._next_doc_id = len(self._doc_id_cache)+1
        self._next_word_id = len(self._doc_id_cache)+1

        # keep track of some info about the page we are currently parsing
        self._curr_depth = 0
        self._curr_url = ""
        self._curr_doc_id = 0
        self._font_size = 0
        self._curr_words = None

        # get all urls into the queue
        if spec_url != "0":
            self._url_queue.append((spec_url,0))
        else:
            try:
                with open(url_file, 'r') as f:
                    for line in f:
                        self._url_queue.append((self._fix_url(line.strip(), ""), 0))
            except IOError:
                #print "No (valid) file selected!"
                pass

    def get_inverted_index(self):
        """
        A function to get inverted index
        :return:
        """
        return self._inverted_index_dict

    def get_resolved_inverted_index(self):
        """
        A function that resolves the inverted index
        :return:
        """
        return self._resolved_inverted_index_dict

    def get_page_rank_list(self, redis_server, links_list):
        """
        A function that gets the page rank list and stores in redis
        :return:
        """
        self._page_rank_list = page_rank(self._links_list)

        # print self._page_rank_list

        self.redis_server.hmset("page_rank_dict", self._page_rank_list)

    def _insert_document(self, url):
        """
        A function that puts the document in a predefined dictionary with the "doc_id"
        as the the value, and the url as the key
        :param url:
        :return:
        """
        ret_id = self._next_doc_id
        self._doc_id_cache[url] = ret_id
        self._next_doc_id += 1

        return ret_id

    def _insert_word(self, word):
        """
        A function that puts the word in a predefined dictionary with the "word_id"
        as the the value, and the word as the key
        :param word:
        :return:
        """
        ret_id = self._next_word_id
        self._word_id_cache[word] = ret_id
        self._next_word_id += 1
        return ret_id

    def word_id(self, word):
        """Get the word id of some specific word."""
        if word in self._word_id_cache:
            # If word already exists then it will be in the inverted index dict, so just add the doc id to the set
            self._inverted_index_dict[self._word_id_cache[word]].add(self._curr_doc_id)
            self._resolved_inverted_index_dict[word].add(self._curr_url)

            # Add to resolved inverted index to set on redis
            set_doc_id = pickle.loads(self.redis_server.hget("wordTodoc", word))

            set_doc_id.add(self._curr_doc_id)

            self.redis_server.hset("wordTodoc", word, pickle.dumps(set_doc_id))

            return self._word_id_cache[word]

        word_id = self._insert_word(word)
        self._word_id_cache[word] = word_id

        # Add word to lexicon
        self._word_lexicon.append(word)

        # If it is the first time encountering the word then make a new entry in the inverted index dictionary
        self._inverted_index_dict[word_id] = set([self._curr_doc_id])
        self._resolved_inverted_index_dict[word] = set([self._curr_url])

        # add a set of doc_id per word_id to redis
        self.redis_server.hsetnx("wordTodoc", word, pickle.dumps(set([self._curr_doc_id])))

        return word_id

    def document_id(self, url):
        """Get the document id for some url."""
        if url in self._doc_id_cache:
            return self._doc_id_cache[url]

        if self._curr_depth <= depth_glob:
            doc_id = self._insert_document(url)
            self._doc_id_cache[url] = doc_id
            self._document_index.append([doc_id, url])
            self._document_index.sort()
            # add_to_list(self.redis_server, "Document_index", url)
            self.redis_server.hset("Document_index_dict", doc_id, url)
        return doc_id

    def _fix_url(self, curr_url, rel):
        """Given a url and either something relative to that url or another url,
        get a properly parsed url."""

        rel_l = rel.lower()
        if rel_l.startswith("http://") or rel_l.startswith("https://"):
            curr_url, rel = rel, ""

        # compute the new url based on import
        curr_url = urlparse.urldefrag(curr_url)[0]
        parsed_url = urlparse.urlparse(curr_url)
        return urlparse.urljoin(parsed_url.geturl(), rel)

    def add_link(self, from_doc_id, to_doc_id):
        """Add a link into the database, or increase the number of links between
        two pages in the database."""

        self._links_list.append((from_doc_id, to_doc_id))
        # TODO

    def _visit_title(self, elem):
        """Called when visiting the <title> tag."""
        title_text = self._text_of(elem).strip()
        self._document_index[self._curr_doc_id - 1].append(title_text)
        self.redis_server.hset("Document_index_title", self._curr_url, title_text)
        #print self._curr_doc_id
        #print title_text
        #print "document title="+ repr(title_text)

        # TODO update document title for document id self._curr_doc_id

    def _visit_a(self, elem):
        """Called when visiting <a> tags."""

        dest_url = self._fix_url(self._curr_url, attr(elem,"href"))

        #print "href="+repr(dest_url), \
        #      "title="+repr(attr(elem,"title")), \
        #      "alt="+repr(attr(elem,"alt")), \
        #      "text="+repr(self._text_of(elem))

        # add the just found URL to the url queue
        self._url_queue.append((dest_url, self._curr_depth))

        # add a link entry into the database from the current document to the
        # other document
        self.add_link(self._curr_doc_id, self.document_id(dest_url))

        # TODO add title/alt/text to index for destination url

    def _add_words_to_document(self):
        # TODO: knowing self._curr_doc_id and the list of all words and their
        #       font sizes (in self._curr_words), add all the words into the
        #       database for this document
        #print "    num words="+ str(len(self._curr_words))
        return

    def _increase_font_factor(self, factor):
        """Increade/decrease the current font size."""
        def increase_it(elem):
            self._font_size += factor
        return increase_it

    def _visit_ignore(self, elem):
        """Ignore visiting this type of tag"""
        pass

    def _add_text(self, elem):
        """Add some text to the document. This records word ids and word font sizes
        into the self._curr_words list for later processing."""
        words = WORD_SEPARATORS.split(elem.string.lower())
        for word in words:
            word = word.strip()
            if word in self._ignored_words:
                continue
            self._curr_words.append((self.word_id(word), self._font_size))

    def _text_of(self, elem):
        """Get the text inside some element without any tags."""
        if isinstance(elem, Tag):
            text = [ ]
            for sub_elem in elem:
                text.append(self._text_of(sub_elem))

            return " ".join(text)
        else:
            return elem.string

    def _index_document(self, soup):
        """Traverse the document in depth-first order and call functions when entering
        and leaving tags. When we come across some text, add it into the index. This
        handles ignoring tags that we have no business looking at."""
        class DummyTag(object):
            next = False
            name = ''

        class NextTag(object):
            def __init__(self, obj):
                self.next = obj

        tag = soup.html
        stack = [DummyTag(), soup.html]

        while tag and tag.next:
            tag = tag.next

            # html tag
            if isinstance(tag, Tag):

                if tag.parent != stack[-1]:
                    self._exit[stack[-1].name.lower()](stack[-1])
                    stack.pop()

                tag_name = tag.name.lower()

                # ignore this tag and everything in it
                if tag_name in self._ignored_tags:
                    if tag.nextSibling:
                        tag = NextTag(tag.nextSibling)
                    else:
                        self._exit[stack[-1].name.lower()](stack[-1])
                        stack.pop()
                        tag = NextTag(tag.parent.nextSibling)

                    continue

                # enter the tag
                self._enter[tag_name](tag)
                stack.append(tag)

            # text (text, cdata, comments, etc.)
            else:
                self._add_text(tag)

    def crawl(self, depth=2, timeout=3):
        """Crawl the web!"""
        seen = set()

        #global variable for the entire document, so anything beyond the depth isn't searched.
        global depth_glob
        depth_glob = depth

        while len(self._url_queue):
            url, depth_ = self._url_queue.pop()

            # skip this url; it's too deep
            if depth_ > depth:
                continue

            if depth_ == 0:
               self._curr_depth = 0

            doc_id = self.document_id(url)

            # we've already seen this document
            if doc_id in seen:
                continue

            seen.add(doc_id) # mark this document as haven't been visited

            socket = None
            try:
                socket = urllib2.urlopen(url, timeout=timeout)
                soup = BeautifulSoup(socket.read())

                #if soup.title:
                #    self._document_index[doc_id - 1].append(soup.title.string)
                #else:
                #    self._document_index[doc_id - 1].append("No title")

                self._curr_depth = depth_ + 1
                self._curr_url = url
                self._curr_doc_id = doc_id
                self._font_size = 0
                self._curr_words = []
                self._index_document(soup)
                self._add_words_to_document()
                # print self._curr_words
                # print "    url="+repr(self._curr_url)
            except Exception as e:
                pass
            finally:

                if socket:
                    socket.close()
        self.get_page_rank_list(self.redis_server, self._links_list)


if __name__ == "__main__":
    bot = crawler(None, "urls.txt")
    bot.crawl(depth=1)

