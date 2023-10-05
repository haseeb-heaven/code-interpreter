import tablue

# Open the CSV file
with open('/Users/haseeb-mir/Downloads/emps.csv', 'r') as f:
    # Read the CSV data into a list of lists
    data = [row for row in csv.reader(f)]

# Create a Tablue table from the data
table = tablue.Table(data)

# Display the table
table.show()
