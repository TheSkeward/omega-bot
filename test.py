"""test function"""
import main


def test_scott_post_helper():
    failure = False
    queries = ("", "melatonin")
    for term in queries:
        try:
            main.search_helper(term, "7e281d64bc7d22cb7")
        except FileNotFoundError:
            print("FAILURE: test_scott_post_helper()")
            print(
                "Expected a random Scott article from scott_links.txt "
                "but got a File Not Found error"
            )
            failure = True
        except KeyError:
            print("FAILURE: test_scott_post_helper()")
            print(
                f"Expected search result for "
                "'https://www.googleapis.com/customsearch/v1?key="
                f"{main.GOOGLE_API_KEY}&cx"
                f"=7e281d64bc7d22cb7&q={term}' but got a KeyError"
            )
            failure = True
    if not failure:
        print("SUCCESS: test_scott_post_helper()")


print("----------------------------------------------------------------------")
print("Testing scott_post_helper...")
test_scott_post_helper()
print("All done!")
