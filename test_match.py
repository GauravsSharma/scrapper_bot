# test_match.py
from jobs import match_role, match_location, match

# Role matching tests
assert match_role("Node.js Developer")
assert match_role("Full Stack Engineer")
assert match_role("AI Engineer")
assert match_role("Software Engineering Intern")
assert match_role("SDE Intern")
assert match_role("Web Development Intern")
assert match_role("Backend Software Developer")
assert match_role("Junior Ubuntu Software Engineer")

# Role exclusion tests
assert not match_role("Senior Node.js Developer")
assert not match_role("Tech Lead - Backend")
assert not match_role("Sales Manager")
assert not match_role("Global Tax Intern")
assert not match_role("Talent Acquisition Intern")
assert not match_role("Talent Acquisition Intern - IT Recruitment")
assert not match_role("Product Manager")
assert not match_role("HR Intern")

# Location matching tests
assert match_location("Remote")
assert match_location("Remote (Worldwide)")
assert match_location("Home based - Worldwide")
assert match_location("Noida, India")
assert match_location("Gurgaon, Haryana")
assert match_location("Gurugram")
assert match_location("Delhi, India")
assert match_location("Agra, Uttar Pradesh")
assert match_location("Work from home")

# Location exclusion tests (Blocked geos or non-target cities without remote)
assert not match_location("Remote (USA)")
assert not match_location("Remote (UK)")
assert not match_location("Remote, Canada; Remote, United States")
assert not match_location("San Francisco, USA")
assert not match_location("Berlin, Germany")
assert not match_location("Bangalore, India")  # On-site in Bangalore not in target cities

# Combined match test
assert match("Node.js Developer", "Remote (Worldwide)")
assert match("Software Engineering Intern", "Noida, India")
assert not match("Senior Full Stack Developer", "Remote")
assert not match("Global Tax Intern", "Remote")
assert not match("Backend Developer", "Remote (USA)")

print("All match_role(), match_location(), and match() tests passed!")
