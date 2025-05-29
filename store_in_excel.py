import pandas as pd
import json

# Load the JSON data
# Make sure 'extracted_tables.json' is in the same directory as the script,
# or provide the full path to the file.
try:
    with open('outputs/extracted_tables.json', 'r') as f:
        json_data = json.load(f)
except FileNotFoundError:
    print("Error: 'extracted_tables.json' not found. Please make sure the file exists in the correct location.")
    exit()
except json.JSONDecodeError:
    print("Error: 'extracted_tables.json' is not a valid JSON file.")
    exit()
except Exception as e:
    print(f"An error occurred while reading the JSON file: {e}")
    exit()

# Prepare data for the new Excel file by flattening the structure
all_rows = []
if not isinstance(json_data, list):
    print("Error: JSON data is not a list of records as expected.")
    exit()

for record_index, record in enumerate(json_data):
    if not isinstance(record, dict):
        print(f"Warning: Item at index {record_index} in JSON data is not a dictionary. Skipping.")
        continue

    base_info = {}
    for key, value in record.items():
        if key != "claims": 
            if key == "Member #" and isinstance(value, str) and value.startswith("Medi-Cal "):
                 base_info[key] = value.replace("Medi-Cal ", "").strip()
            else:
                base_info[key] = value

    claims_data = record.get("claims", [])
    if isinstance(claims_data, list) and claims_data:
        for claim_index, claim in enumerate(claims_data):
            if not isinstance(claim, dict):
                print(f"Warning: Claim at index {claim_index} for record {record_index+1} is not a dictionary. Skipping claim.")
                continue
            
            row_data = base_info.copy()
            row_data.update(claim)
            all_rows.append(row_data)
    elif base_info: 
        # If there are no claims, or claims is not a list, but there's base info
        # This will add a row with only the base information.
        # If you only want rows that have claims, you can remove this elif block.
        print(f"Note: Record {record_index+1} (Member #: {base_info.get('Member #', 'N/A')}) has no 'claims' data or it's not a list. Adding a row with base information only.")
        all_rows.append(base_info) 
    elif not base_info and not claims_data:
         print(f"Warning: Record {record_index+1} is empty or has an unexpected structure. Skipping.")


if not all_rows:
    print("No data was processed or extracted from the JSON. The output file will not be created.")
    exit()

# Create a DataFrame from ALL processed rows
output_df = pd.DataFrame(all_rows)

# Define the name for the NEW Excel file that will be created
output_excel_file = "outputs/output_from_json.xlsx"

try:
    # Save the ENTIRE DataFrame to a NEW Excel file.
    # If 'output_from_json.xlsx' already exists, it will be overwritten.
    output_df.to_excel(output_excel_file, index=False)
    print(f"\nData successfully written to the NEW Excel file: {output_excel_file}")
    print(f"The Excel file should contain {len(output_df)} rows of data.")

    # The following printout is just a SAMPLE for the console (first 5 rows)
    # It does NOT mean the Excel file is limited to 5 rows.
    print("\nSample of first 5 rows (printed to console for quick check):")
    print(output_df.head())
    
    if len(output_df) > 5:
        print("...")
        print(f"(Note: The above is just a sample. The actual Excel file '{output_excel_file}' contains all {len(output_df)} rows.)")

except Exception as e:
    print(f"An error occurred while writing to Excel: {e}")