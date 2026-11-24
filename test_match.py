# test_match.py
from jobs import match_role, match_location, match

# 1. Test with default config (Gaurav's config in config.json)
assert match_role("Node.js Developer")
assert match_role("Full Stack Engineer")
assert match_role("AI Engineer")
assert match_role("Software Engineering Intern")
assert match_role("SDE Intern")
assert match_role("Backend Software Developer")
assert match_role("Junior Ubuntu Software Engineer")

# Role exclusion tests
assert not match_role("Senior Node.js Developer")
assert not match_role("Tech Lead - Backend")
assert not match_role("Sales Manager")
assert not match_role("Global Tax Intern")
assert not match_role("Talent Acquisition Intern")

# Location tests
assert match_location("Remote")
assert match_location("Remote (Worldwide)")
assert match_location("Noida, India")
assert match_location("Gurgaon, Haryana")
assert match_location("Agra, Uttar Pradesh")

# Blocked geos
assert not match_location("Remote (USA)")
assert not match_location("Remote (UK)")
assert not match_location("Bangalore, India")  # Default config is Delhi/NCR/Agra

# 2. Test with Custom Config for another user (e.g. Python Dev in Bangalore)
custom_cfg = {
    "user_name": "Aman",
    "keywords": ["python", "django", "fastapi", "machine learning"],
    "target_cities": ["bangalore", "bengaluru", "hyderabad"],
    "allow_remote": True,
    "prioritize_remote": True,
    "exclude_senior": True,
    "max_jobs": 10
}

assert match_role("Python Developer", custom_cfg)
assert match_role("Django Backend Engineer", custom_cfg)
assert match_role("Machine Learning Intern", custom_cfg)
assert not match_role("Senior Python Developer", custom_cfg)
assert not match_role("React Developer", custom_cfg)  # Not in Aman's keywords

assert match_location("Bangalore, Karnataka", custom_cfg)
assert match_location("Hyderabad, Telangana", custom_cfg)
assert match_location("Remote (Worldwide)", custom_cfg)
assert not match_location("Noida, India", custom_cfg)  # Not in Aman's cities

print("All default and custom personalized config tests passed successfully!")
