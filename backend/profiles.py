import json
import os

PROFILES_FILE = 'profiles.json'

def load_profiles():
    if not os.path.exists(PROFILES_FILE):
        default = {
            'HR Documents': {
                'categories': ['phone','email','dob','pan','aadhaar','ssn','passport'],
                'custom_words': []
            },
            'Medical Records': {
                'categories': ['phone','email','dob','ssn','aadhaar'],
                'custom_words': ['diagnosis','prescription','patient']
            },
            'Legal Contracts': {
                'categories': ['phone','email','pan','passport','credit'],
                'custom_words': ['confidential','attorney','plaintiff']
            }
        }
        save_profiles(default)
        return default
    with open(PROFILES_FILE, 'r') as f:
        return json.load(f)

def save_profiles(profiles):
    with open(PROFILES_FILE, 'w') as f:
        json.dump(profiles, f, indent=2)

def add_profile(name, categories, custom_words):
    profiles = load_profiles()
    profiles[name] = {'categories': categories, 'custom_words': custom_words}
    save_profiles(profiles)
    return profiles

def delete_profile(name):
    profiles = load_profiles()
    if name in profiles:
        del profiles[name]
        save_profiles(profiles)
    return profiles
