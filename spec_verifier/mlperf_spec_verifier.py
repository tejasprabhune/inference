import argparse
import re
import json
from enum import Enum

# Parser for command line
parser = argparse.ArgumentParser(description='Input log, model, and mode.')
parser.add_argument('--log', action='store', type=str,
                    dest='log_filename', help='Path of log file')
parser.add_argument('--spec', action='store', type=str,
                    dest='spec_filename', help='Path of spec JSON file')
parser.add_argument('--model', action='store', type=str, dest='model_name',
                    help='Model name you are testing (e.g. Resnet50-v1.5)')

args = parser.parse_args()

field_compliance = {}

class ExitCode (Enum):
    COMPLIANT = "COMPLIANT"
    SETTING_ERROR = "SETTING_ERROR"
    PARSE_ERROR = "PARSE_ERROR"

# Scrape lines from txt file
with open(args.log_filename) as logfile:
    log_lines = logfile.readlines()

log_lines = [line.strip() for line in log_lines]

# Import JSON file
with open(args.spec_filename) as json_file:
    json_dict = json.load(json_file)

def find_string(iter_list, substring):
    """Return index if a specific substring is inside each string in a list."""
    for i, s in enumerate(iter_list):
        if substring in s:
            return i


effective_string = 'Effective Settings:'
requested_string = 'Requested Settings:'

effective_index = find_string(log_lines, effective_string)
requested_index = find_string(log_lines, requested_string)

if effective_index == None or requested_index == None:
  print("\nUnable to parse log file properly. Please check for any errors.")
  exit_code = ExitCode.PARSE_ERROR

effective_settings = log_lines[effective_index+1:requested_index-1]
effective_dict = {}


# Find every ":" in each line
def find_char(character, string):
    """Returns index for every time a character is found in a string."""
    char_counter = []
    for m in re.finditer(character, string):
        char_counter.append(m.start())
    return char_counter


def slice_char(string, character, index, find_char_results):
    """Slices a string to remove everything before a specific character."""
    # + 2 because the first character of the attribute exists 2 characters after the colon.
    return string[find_char_results[index] + 2:]


def get_key_value(string, character, index, find_char_results):
    find_char_result = find_char_results[index]

    """Creates a list with a key value pair from parsed log file line."""
    # + 2 because the first character of the attribute exists 2 characters after the colon.
    value = string[find_char_result + 2:]
    if value.isdigit():
        value = int(value)
    return [string[0: find_char_result].strip(), value]


for i, s in enumerate(effective_settings):
    """Parses the effective settings list and creates a dictionary out of it."""
    find_char_results = find_char(effective_settings[i], ':')
    # 3 used below because the attributes exist after the 4th colon.
    effective_settings[i] = slice_char(effective_settings[i], ':', 3, find_char_results)
    get_key_value_result = get_key_value(effective_settings[i], ':', 0, find_char_results)
    effective_dict[get_key_value_result[0]] = get_key_value_result[1]

effective_keys = list(effective_dict.keys())
exit_code = ExitCode.COMPLIANT
field_compliance = {}
# first iterate through the Scenarios list

if effective_dict["Scenario"] not in json_dict.keys():
    """Checks if scenario exists"""
    exit_code = ExitCode.PARSE_ERROR
else:
    scenario = effective_dict["Scenario"]
    field_compliance = dict((el, False) for el in json_dict[scenario].keys())
    field_compliance["Scenario"] = True

    for a in json_dict[scenario]:
        """Checks each attribute"""
        spec_value = json_dict[scenario][a]
        
        if a == "target_latency (ns)":
            if scenario == "MultiStream" or scenario == "Server":
                current_keys = list(spec_value.keys())

                if args.model_name in current_keys:
                    if spec_value[args.model_name] == effective_dict[a]:
                        field_compliance[a] = True
            else:
                field_compliance[a] = True
        elif a == "min_query_count":
            if scenario == "MultiStream" or scenario == "Server":
                spec_keys = list(spec_value.keys())

                if args.model_name in current_keys:
                    if spec_value[args.model_name] <= effective_dict[a]:
                        field_compliance[a] = True
            else:
                if spec_value <= effective_dict[a]:
                        field_compliance[a] = True
        elif a == "samples_per_query":
            if scenario == "Offline":
                if spec_value <= effective_dict[a]:
                    field_compliance[a] = True
            elif scenario == "MultiStream":
                field_compliance[a] = True
        elif a == "min_duration (ms)":
            if spec_value <= effective_dict[a]:
                field_compliance[a] = True
        elif a == "min_sample_count":
            if scenario == "Server":
                spec_keys = list(spec_value.keys())

                if args.model_name in current_keys:
                    if spec_value[args.model_name] <= effective_dict[a]:
                        field_compliance[a] = True
            else:
                if spec_value <= effective_dict[a]:
                        field_compliance[a] = True
        elif effective_dict[a] == spec_value:
            field_compliance[a] = True

if exit_code is not ExitCode.PARSE_ERROR:
    """Sets final exit code value"""
    if all(value == True for value in field_compliance.values()) == True:
        exit_code = ExitCode.COMPLIANT
    else:
        exit_code = ExitCode.SETTING_ERROR


if exit_code == ExitCode.COMPLIANT:
    print("\nSummary: Your TestSettings are compliant with the MLPerf specifications.")
elif exit_code == ExitCode.SETTING_ERROR:
    print("\nSummary: One or more of your TestSettings is not compliant with the MLPerf specifications. Please examine below to see which attributes do not comply.")
else:
    print("\nSummary: There is an error with parsing the log file. Please fix before continuing the test.")

print("\nExit Code: " + exit_code.value + "\n")
print("Attribute Complies? \n" + str(field_compliance) + "\n")
