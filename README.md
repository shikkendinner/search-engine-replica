# CSC326 Search Engine Project
A project I did for my Programming Languages course at University of Toronto. I was tasked with building a website that mimics Google's search engine.

## How It Works
The frontend presents a simple query interface to the web user, which asks for a single keyword at minimum. In response to the user query, the frontend responds by searching the keyword against the indexed database of URLs built by the backend. The returned URL should is displayed in sorted order according to a ranked score computed in advance by the backend.
 
The backend takes an arbitrary file named urllist.txt, which contains one URL per line, and builds an inverted index database which maps each keyword to URLs. In addition, each URL is assigned a page rank using a page rank algorithm.
