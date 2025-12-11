import sqlite3 as sql
from flask import Flask, render_template, request, redirect, url_for, Response, flash
import pandas as pd
import io


def create_db():
    connection = sql.connect('database.db')
    cursor = connection.cursor()
    cursor.execute(''' CREATE TABLE IF NOT EXISTS data_table (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   unit REAL,
                   date_sub TEXT,
                   date_exp TEXT,
                   item TEXT,
                   amt_due REAL,
                   amt_rec REAL,
                   bal_tot REAL,
                   comment TEXT)
                   ''')
    connection.commit()
    connection.close()

create_db()

app = Flask(__name__)
app.secret_key = 'crazy_frog'  # Needed for flash messages


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_data():
    date_sub = request.form['date_sub']
    unit = request.form['unit']
    date_exp = request.form['date_exp']
    item = request.form['item']
    amt_due = request.form['amt_due']
    amt_rec = request.form['amt_rec']
    comment = request.form['comment']

    connection = sql.connect('database.db')
    cursor = connection.cursor()

    query = "SELECT * FROM data_table WHERE unit=? ORDER BY id DESC LIMIT 1"
    df = pd.read_sql(query, connection, params=(unit,))

    if len(df) == 0:
        bal_tot = float(amt_due) - float(amt_rec)
    else:
        recent_amt = float(df['bal_tot'])
        if float(amt_due) > 0:
            bal_tot = recent_amt + float(amt_due)
            bal_tot = round(bal_tot, 2)
        if float(amt_rec) > 0:
            bal_tot = recent_amt - float(amt_rec)
            bal_tot = round(bal_tot, 2)

    cursor.execute("INSERT INTO data_table (date_sub, unit, date_exp, item, amt_due, amt_rec, bal_tot, comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (date_sub, unit, date_exp, item, amt_due, amt_rec, bal_tot, comment))
    connection.commit()
    connection.close()

    flash('Data successfully submitted!', 'success')
    return redirect(url_for('home'))

@app.route('/export_xlsx', methods=['GET'])
def export_xlsx():
    connection = sql.connect('database.db')
    query = "SELECT * FROM data_table"
    df = pd.read_sql(query, connection)
    connection.close()

    df.loc[df['unit'] == 24, 'unit'] = '24th Ave'
    df.loc[df['unit'] == 72, 'unit'] = '72nd St'
    df.loc[df['unit'] == 11, 'unit'] = 'Unit 11'
    df.loc[df['unit'] == 13, 'unit'] = 'Unit 13'


    df = df.rename(columns={'id': 'ID', 'unit': 'Unit', 'date_sub': 'Date of Submission', 'date_exp': 'Date of Expense/Payment', 'item': 'Expense/Payment', 'amt_due': 'Amount Due', 'amt_rec': 'Amount Received', 'bal_tot': 'Total Balance', 'comment': 'Comments'})



    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')  # Write DataFrame to sheet 'Data'



    output.seek(0)

    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=data_table.xlsx"})


@app.route('/report', methods=['GET', 'POST'])
def report():
    error = None
    inc= None
    exp = None
    table_data = None
    unit = None
    other_table = None
    ten_bal = None

    if request.method == 'POST':

        unit = request.form['unit']

        connection = sql.connect('database.db')
        query = "SELECT * FROM data_table WHERE unit=? ORDER BY id ASC"
        df = pd.read_sql(query, connection, params=(unit,))
        connection.close()

        print(df)

        inc = df['amt_rec'].sum()
        inc = round(inc, 2)
        exp = df['amt_due'].sum()
        exp = round(exp, 2)

        rent_tot = df[df['item'].str.contains('Rent')]['amt_due'].sum()
        hous_tot = df[df['item'].str.contains('Housing Payment')]['amt_rec'].sum()
        ten_tot = df[df['item'].str.contains('Tenant Payment')]['amt_rec'].sum()

        ten_bal = round(rent_tot - (hous_tot + ten_tot), 2)

        connection = sql.connect('database.db')
        query = """
            SELECT item,
                date_exp,
                SUM(amt_due) AS total_amt_due,
                SUM(amt_rec) AS total_amt_rec,
                SUM(amt_due + amt_rec) AS Amount
            FROM data_table
            WHERE unit=?
            GROUP BY item
        """
        df = pd.read_sql(query, connection, params=(unit,))
        connection.close()

        tax_year = request.form['tax_year']

        df = df.loc[df['date_exp'].str.startswith(tax_year)]

        df_sub = df.drop(columns=['total_amt_due', 'total_amt_rec', 'date_exp'])

        df_sub['Amount'] = df_sub['Amount'].round(2)

        table_data = df_sub.to_html(classes='table table-bordered', index=False)

        connection = sql.connect('database.db')
        query = """
            SELECT item,
                amt_due AS total_amt_due,
                amt_rec AS total_amt_rec,
                amt_due + amt_rec AS Amount,
                comment
            FROM data_table
            WHERE unit=?
        """
        df = pd.read_sql(query, connection, params=(unit,))
        connection.close()

        df = df.loc[df['comment'].str.strip().ne('')]

        df = df.groupby('comment')['Amount'].sum().reset_index()

        other_table = df.to_html(classes='table table-bordered', index=False)


    return render_template('report.html', inc=inc, exp=exp, error=error, data = table_data, unit = unit, other_data = other_table, ten_bal = ten_bal)

@app.route('/summary', methods=['POST', 'GET'])
def summary():
    connection = sql.connect('database.db')
    query = "SELECT * FROM data_table ORDER BY unit, date_exp ASC"
    df = pd.read_sql(query, connection)
    connection.close()

    # Data cleaning
    df.loc[df['unit'] == 24, 'unit'] = '24th Ave'
    df.loc[df['unit'] == 72, 'unit'] = '72nd St'
    df.loc[df['unit'] == 11, 'unit'] = 'Unit 11'
    df.loc[df['unit'] == 13, 'unit'] = 'Unit 13'

    # Rename columns
    df = df.rename(columns={'id': 'ID', 'unit': 'Unit', 'date_sub': 'Date of Submission', 'date_exp': 'Date of Expense/Payment', 'item': 'Expense/Payment', 'amt_due': 'Amount Due', 'amt_rec': 'Amount Received', 'bal_tot': 'Total Balance', 'comment': 'Comments'})

    df['Total Balance'] = df['Total Balance'].round(2)

    #df = df.to_html(classes='table table-bordered', index=False)
    return render_template('summary.html', data=df)


@app.route('/delete/<int:row_id>', methods=['GET'])
def delete_row(row_id):
    connection = sql.connect('database.db')
    cursor = connection.cursor()

    # Step 1: Retrieve the row to be deleted
    query = "SELECT * FROM data_table WHERE id = ?"
    cursor.execute(query, (row_id,))
    deleted_row = cursor.fetchone()

    if deleted_row:
        amt_due_deleted = deleted_row[5]  # Amount Due column index (0-based)
        amt_rec_deleted = deleted_row[6]  # Amount Received column index (0-based)

        # Step 2: Delete the row from the table
        cursor.execute("DELETE FROM data_table WHERE id = ?", (row_id,))
        connection.commit()

        # Step 3: Get all rows after the deleted row, ordered by ID
        cursor.execute("SELECT * FROM data_table WHERE id > ? ORDER BY id ASC", (row_id,))
        subsequent_rows = cursor.fetchall()

        # Step 4: Update each subsequent row's bal_tot
        for row in subsequent_rows:
            row_id = row[0]  # Row ID (index 0)
            previous_bal_tot = row[7]  # Previous Total Balance column index (0-based)
            # Adjusting based on whether amt_due or amt_rec is used
            if amt_due_deleted > 0:
                # The deleted row had an amount due, so subtract it from the next row's bal_tot
                new_bal_tot = previous_bal_tot - amt_due_deleted 
            else:
                # The deleted row had an amount received, so add it to the next row's bal_tot
                new_bal_tot = previous_bal_tot + amt_rec_deleted

            # Step 5: Update the current row's Total Balance in the database
            cursor.execute("UPDATE data_table SET bal_tot = ? WHERE id = ?", (new_bal_tot, row_id))
            connection.commit()

        flash('Row deleted and Total Balance updated!', 'success')
    else:
        flash('Row not found.', 'danger')

    connection.close()
    return redirect(url_for('summary'))



if __name__ == '__main__':
    app.run(debug=True)





