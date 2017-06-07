# CSC326 Search Engine Project
A project I did for my Programming Languages course at University of Toronto. I was tasked with building a website that mimics Google's search engine.

## How It Works
The frontend presents a simple query interface to the web user, which asks for a single keyword at minimum. In response to the user query, the frontend responds by searching the keyword against the indexed database of URLs built by the backend. The returned URL is displayed in sorted order according to a ranked score computed in advance by the backend.
 
The backend takes an arbitrary file named urls.txt, which contains one URL per line, and builds an inverted index database which maps each keyword to URLs (see crawler.py). In addition, each URL is assigned a page rank using a page rank algorithm (see pagerank.py). The database used to store these mappings is a Redis database.

## What Has Been Used
* Bottle web framework to run the web server (Python)
* HTML, CSS, and basic Javascript to manipulate the frontend and communicate with the web server
* Google's API to implement a sign-in feature (registration with the Google Console required)
* Beaker library for session management (Python)
* Redis database to store mappings

## Setup, Installing, and Running the Search Engine
In order to setup this, you will need to download and install a few libraries. Follow the instructions in the links below:
* [Bottle](http://bottlepy.org/docs/dev/)
* [Beaker](https://pypi.python.org/pypi/Beaker?)
* [Google API Python Client](https://github.com/google/google-api-python-client)
* [Redis](https://redis.io/topics/quickstart)
* [Redis Python Client](https://pypi.python.org/pypi/redis)

In order to run this:
1. Run the redis server by typing `redis-server` in the terminal (meant to run on only localhost)
2. The backend/urls.txt contains all the URLs that will be crawled by backend/crawler.py and stored into the database (when you search, only these URLs can show up). Modify this file to include as many urls as you like (the more the URLs, the longer it will take for crawler.py to run.
3. While in the project directory, run `python backend/crawler.py` in the terminal. This will populate the redis database with keywords mapped to URLs.
4. While in the project directory, type `python backend/searchEngine.py` in the terminal. This runs the web server on http://localhost:8080/
5. Enjoy!
