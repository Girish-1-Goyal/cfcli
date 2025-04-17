#!/usr/bin/env python3
import os
import json
import time
import random
import string
import hashlib
import requests
import click
import colorama
from colorama import Fore, Style
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import re
from typing import Dict, List, Optional, Any, Tuple
import sys
from urllib.parse import urljoin

# Initialize colorama
colorama.init()

# Load environment variables
load_dotenv()

# Constants
CF_API_BASE = "https://codeforces.com/api/"
CF_BASE_URL = "https://codeforces.com/"
CACHE_DIR = Path.home() / ".cfcli" / "cache"
DEFAULT_TEMPLATE_DIR = Path.home() / ".cfcli" / "templates"
CACHE_TTL = 300  # 5 minutes

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class CFSession:
    def __init__(self):
        self.handle = os.getenv("CF_HANDLE")
        self.api_key = os.getenv("CF_API_KEY")
        self.api_secret = os.getenv("CF_API_SECRET")
        self.session = requests.Session()
        self.csrf_token = None
        self.logged_in = False

    def is_authenticated(self) -> bool:
        return self.handle and self.api_key and self.api_secret

    def api_auth_params(self) -> Dict[str, str]:
        """Generate authentication parameters for API requests"""
        if not self.is_authenticated():
            raise ValueError("Not authenticated. Please run 'cfcli login' first.")

        # Generate random string for request identification
        rand = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        
        # Current Unix time
        current_time = str(int(time.time()))
        
        # Method specific parameters will be added by the caller
        params = {
            "apiKey": self.api_key,
            "time": current_time,
            "rand": rand
        }
        
        return params

    def sign_request(self, method: str, params: Dict[str, str]) -> Dict[str, str]:
        """Add API signature to request parameters"""
        # Sort parameters by key
        sorted_keys = sorted(params.keys())
        signature_string = f"{method}?"
        
        # Construct signature string
        for key in sorted_keys:
            signature_string += f"{key}={params[key]}&"
        
        # Remove trailing '&' and append API secret
        signature_string = signature_string.rstrip('&') + f"#{self.api_secret}"
        
        # Calculate SHA512 hash
        signature = hashlib.sha512(signature_string.encode('utf-8')).hexdigest()
        
        # Add signature to parameters
        params["apiSig"] = f"123456{signature}"
        
        return params

    def call_api(self, method: str, params: Optional[Dict[str, str]] = None) -> Dict:
        """Make an authenticated call to the Codeforces API"""
        if params is None:
            params = {}

        cache_key = f"{method}_{hash(frozenset(params.items()))}"
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data

        url = urljoin(CF_API_BASE, method)
        
        if self.is_authenticated() and method != "user.info":  # user.info is used to verify credentials
            auth_params = self.api_auth_params()
            params.update(auth_params)
            params = self.sign_request(method, params)

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK":
                self._save_to_cache(cache_key, data)
                return data
            else:
                raise Exception(f"API Error: {data.get('comment', 'Unknown error')}")
        except requests.RequestException as e:
            print(f"{Fore.RED}Network error: {e}{Style.RESET_ALL}")
            self._retry_with_backoff(lambda: self.call_api(method, params))
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
            raise

    def web_login(self) -> bool:
        """Log in to Codeforces website to obtain CSRF token and cookies"""
        if not self.handle:
            print(f"{Fore.RED}Handle not set. Please run 'cfcli login' first.{Style.RESET_ALL}")
            return False

        # First, get CSRF token
        try:
            response = self.session.get(CF_BASE_URL)
            response.raise_for_status()
            
            # Extract CSRF token
            csrf_pattern = r'name="X-Csrf-Token" content="([^"]+)"'
            match = re.search(csrf_pattern, response.text)
            
            if not match:
                print(f"{Fore.RED}Could not extract CSRF token.{Style.RESET_ALL}")
                return False
                
            self.csrf_token = match.group(1)
            
            # Now login
            login_data = {
                "handleOrEmail": self.handle,
                "action": "enter",
                "csrf_token": self.csrf_token
            }
            
            login_url = urljoin(CF_BASE_URL, "enter")
            response = self.session.post(login_url, data=login_data)
            
            if "Invalid handle/email or password" in response.text:
                print(f"{Fore.RED}Login failed. Please check your credentials.{Style.RESET_ALL}")
                return False
                
            self.logged_in = True
            return True
            
        except requests.RequestException as e:
            print(f"{Fore.RED}Network error during login: {e}{Style.RESET_ALL}")
            return False

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get data from cache if valid"""
        cache_file = CACHE_DIR / f"{key}.json"
        if not cache_file.exists():
            return None
            
        # Check if cache is still valid
        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - file_time > timedelta(seconds=CACHE_TTL):
            return None
            
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _save_to_cache(self, key: str, data: Dict) -> None:
        """Save data to cache"""
        cache_file = CACHE_DIR / f"{key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except IOError:
            print(f"{Fore.YELLOW}Warning: Could not cache data.{Style.RESET_ALL}")

    def _retry_with_backoff(self, func, max_retries=3, base_delay=1):
        """Retry a function with exponential backoff"""
        for attempt in range(max_retries):
            delay = base_delay * (2 ** attempt)
            print(f"{Fore.YELLOW}Retrying in {delay} seconds... (Attempt {attempt+1}/{max_retries}){Style.RESET_ALL}")
            time.sleep(delay)
            
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"{Fore.RED}Max retries reached. Giving up.{Style.RESET_ALL}")
                    raise


# Initialize global session
cf_session = CFSession()


@click.group()
def cli():
    """Codeforces CLI - Automate your CP workflow"""
    pass


@cli.command()
@click.option('--handle', prompt='Your Codeforces handle', help='Your Codeforces handle', 
              default=lambda: os.getenv("CF_HANDLE", ""))
@click.option('--key', prompt='Your Codeforces API key', help='Your Codeforces API key',
              default=lambda: os.getenv("CF_API_KEY", ""))
@click.option('--secret', prompt='Your Codeforces API secret', help='Your Codeforces API secret',
              default=lambda: os.getenv("CF_API_SECRET", ""))
def login(handle, key, secret):
    """Validate Codeforces credentials"""
    # Set credentials in session
    cf_session.handle = handle
    cf_session.api_key = key
    cf_session.api_secret = secret
    
    # Validate credentials with a test API call
    try:
        response = cf_session.call_api("user.info", {"handles": handle})
        if response and response.get("status") == "OK":
            print(f"{Fore.GREEN}Authentication successful! Welcome, {handle}!{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}Authentication failed. Please check your credentials.{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"{Fore.RED}Error during authentication: {e}{Style.RESET_ALL}")
        return False


@cli.command()
@click.argument('type', type=click.Choice(['upcoming', 'running', 'past']), default='upcoming')
@click.option('--limit', default=5, help='Number of contests to show')
def fetch(type, limit):
    """Fetch contest information"""
    if not cf_session.is_authenticated():
        print(f"{Fore.YELLOW}Not authenticated. Using public API access.{Style.RESET_ALL}")
    
    try:
        response = cf_session.call_api("contest.list")
        contests = response.get("result", [])
        
        # Filter contests based on type
        current_time = int(time.time())
        filtered_contests = []
        
        for contest in contests:
            if type == 'upcoming' and contest.get('phase') == 'BEFORE':
                filtered_contests.append(contest)
            elif type == 'running' and contest.get('phase') == 'CODING':
                filtered_contests.append(contest)
            elif type == 'past' and contest.get('phase') == 'FINISHED':
                filtered_contests.append(contest)
        
        # Sort and limit
        if type == 'upcoming':
            filtered_contests.sort(key=lambda c: c.get('startTimeSeconds', 0))
        else:
            filtered_contests.sort(key=lambda c: c.get('startTimeSeconds', 0), reverse=True)
        
        filtered_contests = filtered_contests[:limit]
        
        # Display contests
        if not filtered_contests:
            print(f"{Fore.YELLOW}No {type} contests found.{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.CYAN}== {type.capitalize()} Contests =={Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'ID':<8} {'Name':<50} {'Start Time':<25} {'Duration'}{Style.RESET_ALL}")
        print("-" * 90)
        
        for contest in filtered_contests:
            start_time = datetime.fromtimestamp(contest.get('startTimeSeconds', 0))
            duration_mins = contest.get('durationSeconds', 0) // 60
            duration_str = f"{duration_mins // 60}h {duration_mins % 60}m"
            
            print(f"{contest.get('id', 'N/A'):<8} {contest.get('name', 'Unknown')[:47]+'...' if len(contest.get('name', '')) > 50 else contest.get('name', 'Unknown'):<50} {start_time.strftime('%Y-%m-%d %H:%M:%S'):<25} {duration_str}")
        
    except Exception as e:
        print(f"{Fore.RED}Error fetching contests: {e}{Style.RESET_ALL}")


@cli.command()
@click.argument('contest_id')
@click.argument('problem_index', required=False)
@click.option('--template-dir', default=None, help='Directory containing C++ templates')
@click.option('--all', is_flag=True, help='Generate files for all problems in the contest')
def generate(contest_id, problem_index, template_dir, all):
    """Generate C++ source files for contest problems"""
    # Validate contest ID
    try:
        contest_id = int(contest_id)
    except ValueError:
        print(f"{Fore.RED}Contest ID must be a number.{Style.RESET_ALL}")
        return

    # Check/create template directory
    if template_dir:
        template_path = Path(template_dir)
    else:
        template_path = DEFAULT_TEMPLATE_DIR
        template_path.mkdir(parents=True, exist_ok=True)

    template_file = template_path / "template.cpp"
    
    # Create default template if it doesn't exist
    if not template_file.exists():
        print(f"{Fore.YELLOW}Template file not found. Creating a basic template...{Style.RESET_ALL}")
        with open(template_file, 'w') as f:
            f.write("""#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <map>
#include <set>

using namespace std;

void solve() {
    // Your solution here
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);
    
    int t = 1;
    // cin >> t;
    while (t--) {
        solve();
    }
    
    return 0;
}
""")

    if all:
        # Fetch contest problems
        try:
            response = cf_session.call_api("contest.standings", {
                "contestId": contest_id,
                "from": 1,
                "count": 1
            })
            
            if response.get("status") != "OK":
                print(f"{Fore.RED}Failed to fetch contest problems.{Style.RESET_ALL}")
                return
                
            problems = response.get("result", {}).get("problems", [])
            
            if not problems:
                print(f"{Fore.YELLOW}No problems found for contest {contest_id}.{Style.RESET_ALL}")
                return
                
            print(f"{Fore.CYAN}Generating files for {len(problems)} problems in contest {contest_id}...{Style.RESET_ALL}")
            
            for problem in problems:
                problem_index = problem.get("index")
                if not problem_index:
                    continue
                    
                # Create output file
                output_filename = f"Contest{contest_id}_{problem_index}.cpp"
                output_path = Path(output_filename)
                
                # Check if file already exists
                if output_path.exists():
                    overwrite = input(f"{Fore.YELLOW}File {output_filename} already exists. Overwrite? (y/N): {Style.RESET_ALL}")
                    if overwrite.lower() != 'y':
                        print(f"{Fore.YELLOW}Skipping {output_filename}{Style.RESET_ALL}")
                        continue
                
                # Generate problem URL
                problem_url = f"https://codeforces.com/contest/{contest_id}/problem/{problem_index}"
                
                try:
                    # Read template
                    with open(template_file, 'r') as src:
                        template_content = src.read()
                    
                    # Add header with problem URL
                    header = f"""/**
 * Problem: Codeforces {contest_id}{problem_index}
 * URL: {problem_url}
 * Date: {datetime.now().strftime('%Y-%m-%d')}
 */
"""
                    # Write to output file
                    with open(output_filename, 'w') as dest:
                        dest.write(header + "\n" + template_content)
                    
                    print(f"{Fore.GREEN}Created {output_filename} successfully!{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Problem URL: {problem_url}{Style.RESET_ALL}")
                    
                except Exception as e:
                    print(f"{Fore.RED}Error generating file {output_filename}: {e}{Style.RESET_ALL}")
                    
        except Exception as e:
            print(f"{Fore.RED}Error fetching contest problems: {e}{Style.RESET_ALL}")
            return
            
    else:
        # Single problem generation (existing code)
        if not problem_index:
            print(f"{Fore.RED}Problem index is required when not using --all flag.{Style.RESET_ALL}")
            return
            
        problem_index = problem_index.upper()
        if not re.match(r'^[A-Z][0-9]?$', problem_index):
            print(f"{Fore.RED}Problem index must be a letter optionally followed by a number (e.g., A, B, C1).{Style.RESET_ALL}")
            return

        # Create output file
        output_filename = f"Contest{contest_id}_{problem_index}.cpp"
        output_path = Path(output_filename)
        
        # Check if file already exists
        if output_path.exists():
            overwrite = input(f"{Fore.YELLOW}File {output_filename} already exists. Overwrite? (y/N): {Style.RESET_ALL}")
            if overwrite.lower() != 'y':
                print(f"{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")
                return

        # Generate problem URL
        problem_url = f"https://codeforces.com/contest/{contest_id}/problem/{problem_index}"
        
        try:
            # Read template
            with open(template_file, 'r') as src:
                template_content = src.read()
            
            # Add header with problem URL
            header = f"""/**
 * Problem: Codeforces {contest_id}{problem_index}
 * URL: {problem_url}
 * Date: {datetime.now().strftime('%Y-%m-%d')}
 */
"""
            # Write to output file
            with open(output_filename, 'w') as dest:
                dest.write(header + "\n" + template_content)
            
            print(f"{Fore.GREEN}Created {output_filename} successfully!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Problem URL: {problem_url}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Error generating file: {e}{Style.RESET_ALL}")


@cli.command()
@click.argument('filename')
def submit(filename):
    """Submit a solution to Codeforces"""
    file_path = Path(filename)
    
    # Check if file exists
    if not file_path.exists():
        print(f"{Fore.RED}File {filename} not found.{Style.RESET_ALL}")
        return
    
    # Extract contest ID and problem index from filename
    match = re.match(r'Contest(\d+)_([A-Z][0-9]?)\.cpp', file_path.name)
    if not match:
        print(f"{Fore.YELLOW}Filename doesn't follow the expected pattern 'Contest{contest_id}_{problem_index}.cpp'.{Style.RESET_ALL}")
        contest_id = click.prompt("Enter contest ID", type=int)
        problem_index = click.prompt("Enter problem index (e.g., A, B, C1)", type=str).upper()
    else:
        contest_id = int(match.group(1))
        problem_index = match.group(2)
    
    # Ensure we're logged in to the website
    if not cf_session.logged_in:
        print(f"{Fore.CYAN}Logging in to Codeforces...{Style.RESET_ALL}")
        if not cf_session.web_login():
            print(f"{Fore.RED}Failed to log in to Codeforces website. Cannot submit.{Style.RESET_ALL}")
            return
    
    # Read source code
    try:
        with open(file_path, 'r') as f:
            source_code = f.read()
    except Exception as e:
        print(f"{Fore.RED}Error reading file: {e}{Style.RESET_ALL}")
        return
    
    # Prepare submission
    submit_url = urljoin(CF_BASE_URL, f"contest/{contest_id}/submit")
    
    # Get CSRF token and cookies if needed
    if not cf_session.csrf_token:
        print(f"{Fore.CYAN}Getting CSRF token...{Style.RESET_ALL}")
        response = cf_session.session.get(submit_url)
        csrf_pattern = r'name="X-Csrf-Token" content="([^"]+)"'
        match = re.search(csrf_pattern, response.text)
        if not match:
            print(f"{Fore.RED}Could not extract CSRF token.{Style.RESET_ALL}")
            return
        cf_session.csrf_token = match.group(1)
    
    # Prepare form data
    submit_data = {
        "csrf_token": cf_session.csrf_token,
        "action": "submitSolutionFormSubmitted",
        "submittedProblemIndex": problem_index,
        "programTypeId": "54",  # ID for C++17
        "source": source_code,
        "tabSize": "4",
        "sourceFile": ""
    }
    
    try:
        print(f"{Fore.CYAN}Submitting solution to problem {problem_index} in contest {contest_id}...{Style.RESET_ALL}")
        response = cf_session.session.post(submit_url, data=submit_data)
        
        if "You have submitted exactly the same code" in response.text:
            print(f"{Fore.YELLOW}Warning: You have submitted exactly the same code before.{Style.RESET_ALL}")
            return
        
        # Check if submission was successful
        if f"contest/{contest_id}/my" in response.url:
            print(f"{Fore.GREEN}Solution submitted successfully!{Style.RESET_ALL}")
            
            # Extract submission ID for status checking
            match = re.search(r'submissionId="(\d+)"', response.text)
            if match:
                submission_id = match.group(1)
                print(f"{Fore.CYAN}Submission ID: {submission_id}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Run 'cfcli status {submission_id}' to check the verdict.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Submission failed. Please check your credentials and try again.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Response URL: {response.url}{Style.RESET_ALL}")
    
    except Exception as e:
        print(f"{Fore.RED}Error submitting solution: {e}{Style.RESET_ALL}")


@cli.command()
@click.argument('submission_id', required=False)
@click.option('--contest-id', type=int, help='Contest ID to check status for all submissions')
def status(submission_id, contest_id):
    """Check submission status"""
    if not submission_id and not contest_id:
        print(f"{Fore.RED}Please provide either a submission ID or a contest ID.{Style.RESET_ALL}")
        return
    
    # Ensure we're logged in to the website
    if not cf_session.logged_in:
        print(f"{Fore.CYAN}Logging in to Codeforces...{Style.RESET_ALL}")
        if not cf_session.web_login():
            print(f"{Fore.RED}Failed to log in to Codeforces website. Cannot check status.{Style.RESET_ALL}")
            return
    
    try:
        if submission_id:
            # Check status for a specific submission
            url = urljoin(CF_BASE_URL, f"data/submitSource")
            params = {"submissionId": submission_id}
            
            print(f"{Fore.CYAN}Checking status for submission {submission_id}...{Style.RESET_ALL}")
            
            # Polling with delay
            max_attempts = 10
            for attempt in range(max_attempts):
                response = cf_session.session.get(url, params=params)
                
                if response.status_code != 200:
                    print(f"{Fore.RED}Error: HTTP {response.status_code}{Style.RESET_ALL}")
                    break
                
                data = response.json()
                verdict = data.get("verdict")
                
                if verdict in ["TESTING", ""]:
                    dots = "." * (attempt + 1)
                    sys.stdout.write(f"\r{Fore.YELLOW}Verdict: In queue{dots}{' ' * 10}{Style.RESET_ALL}")
                    sys.stdout.flush()
                    time.sleep(2)
                    continue
                
                print("")  # Newline after progress dots
                
                # Color based on verdict
                color = Fore.GREEN if verdict == "OK" else Fore.RED
                time_consumed = data.get("timeConsumedMillis", "N/A")
                memory_consumed = data.get("memoryConsumedBytes", "N/A") // 1024  # Convert to KB
                
                print(f"{color}Verdict: {verdict}{Style.RESET_ALL}")
                print(f"Time: {time_consumed} ms")
                print(f"Memory: {memory_consumed} KB")
                
                if "testset" in data and "testCount" in data:
                    passed = data.get("passedTestCount", 0)
                    total = data.get("testCount", 0)
                    print(f"Tests: {passed}/{total}")
                
                break
            else:
                print(f"\n{Fore.YELLOW}Reached maximum polling attempts. Please check the status manually.{Style.RESET_ALL}")
        
        else:
            # Check all submissions for a contest
            url = urljoin(CF_BASE_URL, f"contest/{contest_id}/my")
            response = cf_session.session.get(url)
            
            if "You are not registered" in response.text:
                print(f"{Fore.RED}You are not registered for contest {contest_id}.{Style.RESET_ALL}")
                return
            
            # Parse submissions table
            submissions_pattern = r'data-submission-id="(\d+)".*?data-problemId="\d+".*?data-problemIndex="([^"]+)".*?submissionVerdict="([^"]*)"'
            submissions = re.findall(submissions_pattern, response.text, re.DOTALL)
            
            if not submissions:
                print(f"{Fore.YELLOW}No submissions found for contest {contest_id}.{Style.RESET_ALL}")
                return
            
            print(f"\n{Fore.CYAN}== Submissions for Contest {contest_id} =={Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'ID':<12} {'Problem':<10} {'Verdict':<15}{Style.RESET_ALL}")
            print("-" * 40)
            
            for subm_id, problem_index, verdict in submissions:
                verdict = verdict if verdict else "IN QUEUE"
                color = Fore.GREEN if verdict == "OK" else Fore.RED if verdict not in ["IN QUEUE", "TESTING"] else Fore.YELLOW
                print(f"{subm_id:<12} {problem_index:<10} {color}{verdict}{Style.RESET_ALL}")
            
    except Exception as e:
        print(f"{Fore.RED}Error checking status: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    cli() 