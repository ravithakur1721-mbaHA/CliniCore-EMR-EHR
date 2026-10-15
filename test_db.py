from database import get_table_data

patients = get_table_data("patients")

for p in patients:
    print(p)

from database import get_table_data

labs = get_table_data("lab_results")

for lab in labs:
    print(
        lab["lab_id"],
        lab["visit_id"],
        lab["test_name"],
        lab["result_value"]
    )
