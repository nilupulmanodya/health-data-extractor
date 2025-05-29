import pandas as pd
import json
from typing import List, Dict, Union, Optional, Tuple
from pathlib import Path
from io import BytesIO

def json_to_excel(
    input_json_string: str,
    output_excel_path: Optional[str] = None,
    verbose: bool = True
) -> Tuple[Optional[pd.DataFrame], Optional[bytes]]:
    print("input_json_string", input_json_string)
    try:
        # Handle both string and list inputs
        if isinstance(input_json_string, str):
            json_data = json.loads(input_json_string)
        else:
            json_data = input_json_string  # Already a Python object
    except json.JSONDecodeError:
        if verbose:
            print(f"Error: input is not a valid JSON")
        return None, None
    except Exception as e:
        if verbose:
            print(f"An error occurred while reading the JSON file: {e}")
        return None, None

    # Prepare data for the Excel file by flattening the structure
    all_rows = []
    if not isinstance(json_data, list):
        if verbose:
            print("Error: JSON data is not a list of records as expected")
        return None, None

    for record_index, record in enumerate(json_data):
        if not isinstance(record, dict):
            if verbose:
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
                    if verbose:
                        print(f"Warning: Claim at index {claim_index} for record {record_index+1} is not a dictionary. Skipping claim.")
                    continue
                
                row_data = base_info.copy()
                row_data.update(claim)
                all_rows.append(row_data)
        elif base_info:
            if verbose:
                print(f"Note: Record {record_index+1} (Member #: {base_info.get('Member #', 'N/A')}) has no 'claims' data or it's not a list. Adding a row with base information only.")
            all_rows.append(base_info)
        elif not base_info and not claims_data:
            if verbose:
                print(f"Warning: Record {record_index+1} is empty or has an unexpected structure. Skipping.")

    if not all_rows:
        if verbose:
            print("No data was processed or extracted from the JSON")
        return None, None

    # Create a DataFrame from all processed rows
    output_df = pd.DataFrame(all_rows)

    try:
        # Create Excel file in memory
        excel_buffer = BytesIO()
        output_df.to_excel(excel_buffer, index=False)
        excel_bytes = excel_buffer.getvalue()
        
        # Optionally save to disk if path is provided
        if output_excel_path:
            # Ensure the output directory exists
            Path(output_excel_path).parent.mkdir(parents=True, exist_ok=True)
            # Save the DataFrame to Excel
            output_df.to_excel(output_excel_path, index=False)
            
            if verbose:
                print(f"\nData successfully written to Excel file: {output_excel_path}")
                print(f"The Excel file contains {len(output_df)} rows of data")
                print("\nSample of first 5 rows:")
                print(output_df.head())
                if len(output_df) > 5:
                    print("...")
                    print(f"(Note: The above is just a sample. The actual Excel file contains all {len(output_df)} rows.)")
        
        return output_df, excel_bytes

    except Exception as e:
        if verbose:
            print(f"An error occurred while creating Excel: {e}")
        return None, None
