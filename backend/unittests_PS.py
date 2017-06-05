from crawler import *
import urllib2
import urlparse
from BeautifulSoup import *
from collections import defaultdict
import re
import redis
import pickle
from pagerank import page_rank
from google_test_constants import corr_doc_index
from three_website_test_constant import corr_doc_id_mult

    #wordTodoc:                 key = word_id, value = pickled(set of doc_ids)
    #Document_index_dict:       key = doc_id,  value = url
    #page_rank_dict:            key = doc_id,  value = rank
    
def _unittest_check_wordTodoc(_check_wordTodoc):
    r_actual_ii = _check_wordTodoc._resolved_inverted_index_dict
    actual_ii = _check_wordTodoc._inverted_index_dict
    redis_ii = _check_wordTodoc.redis_server.hgetall("wordTodoc")
    #here, check to see if the size of both hash tables are the same
    if len(actual_ii) != len(redis_ii):
        return False
    
    #here, check if each value of the keys are the same
    for keyA in _check_wordTodoc.redis_server.hkeys("wordTodoc"):
        if actual_ii[_check_wordTodoc._word_id_cache[keyA]] != pickle.loads(redis_ii[keyA]):
            return False
    return True

def _unittest_Document_index_dict(_check_DocIndex_dict):
    #actual_doc_index is a list of lists [[doc_id, url]...]
    actual_doc_index = _check_DocIndex_dict._document_index
    #while redis_doc_index is a hash table with key = doc_id and value = url
    redis_doc_index = _check_DocIndex_dict.redis_server.hgetall("Document_index_dict")
    # print redis_doc_index
    for document in actual_doc_index:
        doc_id = document[0]
        url = document[1]

        if redis_doc_index[str(doc_id)] != url:
            return False
    return True

# This is a function that compares 2 lists of tuples of lists, given in a zip variable.
# Primarily used to compare the document_index lists found from crawler, and the correct value found manually.
def compare_2_lists_of_tuples(zip_var):
    """ The zip variable is of the form [([a001,b001,c001],[a002,b002,c002]), ([a111,b111,c111],[a112,b112,c112]), ...] - list of tuples of lists -
    where the first index refers to the element in the outer list, the second index refers the element in the tuple, and the third element refers to which list the element
    is originally from (1 being from the list generated from the crawler, and 2 being the predefined "correct" list)."""

    """ Look through each element in the zip variable, and compare the first and third elements.
                 -> second element ignored, for it is the URL, and that may change with the domain."""
    for i in range(0, len(zip_var)):
        if zip_var[i][0][0] != zip_var[i][1][0]:			# Compare the first element in each of tuples in the 2 different lists.
            if zip_var[i][0][2] < len(zip_var[i][0])-1:	# If there isn't a title on the document, then we have to compare the URLs (comparing just the doc_ids tells us nothing).
                if zip_var[i][0][2] != zip_var[i][1][2]:	# Check the Titles (the third values).
                    return False
            elif zip_var[i][0][1] != zip_var[i][1][1]:    # Check the URLs (the second values).
                return False
    #returns True if both lists are the same, else False.
    return True
	

# Standard Unit Test, testing the functionality of the crawler function with a valid input.
def google_unittest(google_test):
    #google_test = crawler(None, "unittest_file_google.txt")
    #google_test.crawl(depth = 1)

    """ 'google_test.document_index' and 'corr_doc_index' are both in the form of [[a,b,c],[d,e,f]...]
     where a (and d) is the doc_id, b (and e) is the document URL and c (and f) is the document title."""

    # Create a zip variable for easier comparison between elements in the correct list, and the created list.
    google_zip = zip(google_test._document_index, corr_doc_index)
    """ Can't test any of the functions with words on the document (lexicon, inverted_index, resolved_inverted_index) because there are simply too many words in a single document. """
    return compare_2_lists_of_tuples(google_zip)

# Unit Test to see if the function works for an invalid URL.
def invalid_URL_unittest():
    invalid_test = crawler(None, "invalid_test.txt")
    invalid_test.crawl(depth = 1)

    correct_doc_id = [[1, 'https://ww.google.com']]
    if invalid_test._document_index != correct_doc_id:
        return False
    return True

#Unit Test to see if the function works for several URLS in the same text file.
def several_URL_unittest():
    sev_URL_test = crawler(None, "sev_urls.txt")
    sev_URL_test.crawl(depth = 1)

    # Create a zip variable for easier comparison between elements in the correct list, and the created list.
    sev_URL_zip = zip(sev_URL_test._document_index, corr_doc_id_mult)
    """ Can't test any of the functions with words on the document (lexicon, inverted_index, resolved_inverted_index) because there are simply too many words in a single document. """
    return compare_2_lists_of_tuples(sev_URL_zip)

#Unit Test that checks to see given the wrong output, whether a certain input will still produce an outcome of True or not.
def correct_crawler_out_wrong_comparison_unittest(incor_comp):
    #incor_comp = crawler(None, "unittest_file_google.txt")
    #incor_comp.crawl(depth = 1)

    # Check to see if the doc ids for only google is the same for the google, yahoo and facebook.
    # (should be wrong)
    incorr_doc_index = corr_doc_id_mult
    if len(incorr_doc_index) == len(incor_comp._document_index):
        incorrect_comparison_zip = zip(incor_comp._document_index, incorr_doc_index)
        return compare_2_lists_of_tuples(incorrect_comparison_zip)
    else:
        #if the two lists aren't of the same length, then they must be different.
        return False

#Unit Test to see if document_index is sorted or not.
#s.t. the document_index should be the same regardless of the order of the input.
def diff_order_sev_URL_unittest():
    diff_order_test = crawler(None, "different_order_urls.txt")
    diff_order_test.crawl(depth = 1)

    #compare the output for "urls.txt" to the output of "different_order_urls.txt"
    diff_order_zip = zip(diff_order_test._document_index, corr_doc_id_mult)
    return compare_2_lists_of_tuples(diff_order_zip)

# Unit Test to see if any words are being repeated in the lexicon.
def check_repeated_words_unittest(rep_words):
    #rep_words = crawler(None, "unittest_file_google.txt")
    #rep_words.crawl(depth = 1)
    new_lex = []

    for check_word in rep_words._word_lexicon:
        if check_word in new_lex:
            return False
        else:
            # if the word isn't already in the new lexicon, add it, so we can check to see
            # if another instance of the same word occurs again.
            new_lex.append(check_word)

    # This condition is only met if the program goes through the entire for loop, and none of 
    # the words have been repeated.
    return True

#Unit Test to see if the unresolved inverted index, and the resolved are the same.
def check_resolved_from_unresolved_inverted_index_unittest(res_from_unres):
    #res_from_unres = crawler(None, "unittest_file_google.txt")
    #res_from_unres.crawl(depth = 1)

    unresolved_II = res_from_unres._inverted_index_dict
    resolved_II = res_from_unres._resolved_inverted_index_dict

    # this is a dictionary which we will use to translate the uresolved inverted index
    recreated_unres_II = {}

    # these two for loops parse the entire "resolved_II" (=_resolved_inverted_index_dict) and 
    # converts all the words and urls back into their word_ids and doc_ids respectively.
    # we then recreate the unresolved_inverted_index, and compare the 2 dictionaries.
    for word in resolved_II:
        word_id = res_from_unres._word_id_cache[word]
        recreated_unres_II[word_id] = set([])
        for doc in resolved_II[word]:
            recreated_unres_II[word_id].add(res_from_unres._doc_id_cache[doc])

    # at this point, the entire recreated_unresolved_Inverted_index has been created. 
    # now, we only have to compare the recreated, with the original.
    for word_id in recreated_unres_II:
        set_of_doc_id = recreated_unres_II[word_id]

        # this is in a try statement, because it may be possible that the word_id doesn't exist in the premade
        try:
            premade_set_of_doc_id = unresolved_II[word_id]
            if set_of_doc_id != premade_set_of_doc_id: # here, we check if the sets are the same in both dictionaries.
                return False
        # if the word_id doesn't exist in the unresolved_II that was made by the crawler, then the unresolved_II
        # must not be the same as the recreated_unres_II.
        except Exception as e:
            print e
            return False
    return True


# Main Function
if __name__ == "__main__":
    num_of_incorrect_tests = 0
    run_crawler = crawler(None, "unittest_file_google.txt")
    run_crawler.crawl(depth=1)
    
    
    # Unit test 1
    print " \nCurrently running Unit Test #1 - Standard test with single URL:"
    googleTest_bool = google_unittest(run_crawler)
    if googleTest_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."

    #Unit test 2
    print " \nCurrently running Unit Test #2 - Invalid URL Test:"
    invalidTest_bool = invalid_URL_unittest()
    if invalidTest_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."

    #Unit test 3
    print " \nCurrently running Unit Test #3 - Standard test with multiple URLs:"
    sevURLTest_bool = several_URL_unittest()
    if sevURLTest_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."

    #Unit test 4
    print " \nCurrently running Unit Test #4 - Test with incorrect output:"
    incorComp_bool = correct_crawler_out_wrong_comparison_unittest(run_crawler)
    # We're expecting the value to be false, as we're comparing the value from crawler to the wrong output.
    if incorComp_bool == True:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."

    #Unit test 5
    print " \nCurrently running Unit Test #5 - Sorting test for Document_index:"
    diffOrder_bool = diff_order_sev_URL_unittest()
    if diffOrder_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."

    #Unit test 6
    print " \nCurrently running Unit Test #6 - Repetition test:"
    repeated_words_in_lexicon_bool = check_repeated_words_unittest(run_crawler)
    if repeated_words_in_lexicon_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."

    #Unit test 7
    print "\nCurrently running Unit Test #7 - Check whether the resolved inverted index is the same as the unresolved:"
    check_res_from_unres_bool = check_resolved_from_unresolved_inverted_index_unittest(run_crawler)
    if check_res_from_unres_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."
    
    # Unit test 8
    print " \nCurrently running Unit Test #8 - Checking correctness of word to doc id dictionary in redis:"
    _unittest_check_wordTodoc_bool = _unittest_check_wordTodoc(_check_DocIndex_dict)
    if _unittest_check_wordTodoc_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."
        
    # Unit test 9
    print " \nCurrently running Unit Test #9 - Checking correctness of the doc id to url dictionary in redis:"
    _unittest_Document_index_dict_bool = _unittest_Document_index_dict(_check_DocIndex_dict)
    if _unittest_Document_index_dict_bool == False:
        print "Outcome: Failed."
        num_of_incorrect_tests += 1
    else:
        print "Outcome: Succeeded."
        
    print " \nThe crawler program failed "+str(num_of_incorrect_tests)+" tests."
    if num_of_incorrect_tests == 0:
        print "Congratulations!"
        
        
