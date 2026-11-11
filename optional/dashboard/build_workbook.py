"""Build a portable workbook with literal data and explicit human decision fields."""
from pathlib import Path
import os
import uuid

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

NAVY = '243D5C'
YELLOW = 'FFF1C7'


def literal(cell, value):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = 's'  # User feedback or filenames beginning '=' stay literal.
    cell.alignment = Alignment(vertical='top', wrap_text=True)
    cell.font = Font(name='Calibri', size=11, color='243247')


def header(ws, row, values):
    for column, value in enumerate(values, 1):
        cell = ws.cell(row, column)
        literal(cell, value)
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    ws.row_dimensions[row].height = 32


def build(data, destination):
    destination = Path(destination)
    wb = Workbook()
    summary = wb.active
    summary.title = 'Dashboard'
    detail = wb.create_sheet('Deliverables')
    for sheet in wb:
        sheet.sheet_view.showGridLines = False
    literal(summary['A1'], 'Gaming creator job dashboard')
    summary['A1'].font = Font(name='Calibri', size=20, bold=True, color=NAVY)
    summary.merge_cells('A1:F1')
    for row, text in enumerate([
        'Snapshot at refresh: ' + data['refreshed'],
        'Edit yellow E:H fields on Deliverables. Save and close the workbook, then rerun the dashboard helper.',
        'Passed means every listed human check was performed on every named target. Acceptance is separate.',
        'Counts and production state update on refresh. Missing automated checks remain outstanding.'
    ], 3):
        literal(summary.cell(row, 1), text)
        summary.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        summary.row_dimensions[row].height = 32
    current = [r for r in data['rows'] if r[12] == 'Yes']
    passed = {'Passed - all listed checks performed', 'Previously verified (journal)'}
    metrics = [
        ('Tracked jobs', len(data['jobs'])),
        ('Current revision packages', len(current)),
        ('Production completed (recorded)', sum(r[3] == 'completed' for r in current)),
        ('Human verification recorded', sum(r[4] in passed for r in current)),
        ('Human review pending', sum(r[4] == 'Pending' for r in current)),
        ('Accepted', sum(r[5] == 'Accepted' for r in current)),
        ('Packages with missing files', sum('missing' in r[10].lower() for r in current)),
    ]
    header(summary, 8, ['At last refresh', 'Count'])
    for row, (label, value) in enumerate(metrics, 9):
        literal(summary.cell(row, 1), label)
        literal(summary.cell(row, 2), value)
        summary.row_dimensions[row].height = 25
    header(summary, 18, ['Job', 'Skill', 'Revision', 'Production recorded', 'Human review', 'Acceptance'])
    for number, row in enumerate(current, 19):
        for column, value in enumerate(row[:6], 1):
            literal(summary.cell(number, column), value)
        summary.row_dimensions[number].height = 48
    if not current:
        literal(summary['A19'], 'No registered production jobs yet.')
    for col, width in {'A': 43, 'B': 20, 'C': 23, 'D': 25, 'E': 34, 'F': 22}.items():
        summary.column_dimensions[col].width = width
    summary.freeze_panes = 'C19'
    literal(detail['A1'], 'Deliverables and human verification')
    detail['A1'].font = Font(name='Calibri', size=18, bold=True, color=NAVY)
    detail.merge_cells('A1:I1')
    literal(detail['A2'], 'Edit E:H only. Read the full checklist in I. Use the formula bar or expand the row if text is clipped.')
    detail.merge_cells('A2:I2')
    detail.row_dimensions[2].height = 32
    literal(detail['A3'], 'Each row binds decisions to exact files and requirements. Keep historical rows. Do not select Passed without doing the checks.')
    detail.merge_cells('A3:I3')
    detail.row_dimensions[3].height = 32
    header(detail, 5, data['headers'])
    for number, row in enumerate(data['rows'], 6):
        for column, value in enumerate(row, 1):
            cell = detail.cell(number, column)
            literal(cell, value)
            if 5 <= column <= 8:
                cell.fill = PatternFill('solid', fgColor=YELLOW)
                cell.protection = Protection(locked=False)
            if column in (14, 15) and value:
                cell.hyperlink = Path(value).resolve().as_uri()
        lines = sum(max(1, (len(line) + 89) // 90) for line in row[8].split('\n'))
        detail.row_dimensions[number].height = max(100, min(409, lines * 16 + 16))
    last = max(6, len(data['rows']) + 5)
    if data['rows']:
        table = Table(displayName='DeliverableRecords', ref=f'A5:P{last}')
        table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=False)
        detail.add_table(table)
    for col, key in [('E', 'human'), ('F', 'acceptance'), ('G', 'disposal')]:
        values = ','.join(data['manual'][key])
        validation = DataValidation(type='list', formula1='"' + values + '"', allow_blank=False)
        validation.errorTitle = 'Choose a listed value'
        validation.error = 'Use the dropdown; refresh validates each saved decision.'
        validation.showErrorMessage = True
        detail.add_data_validation(validation)
        validation.add(f'{col}6:{col}{last}')
    widths = {'A': 30, 'B': 20, 'C': 24, 'D': 24, 'E': 36, 'F': 24, 'G': 26, 'H': 40,
              'I': 100, 'J': 60, 'K': 32, 'L': 60, 'M': 20, 'N': 42, 'O': 42, 'P': 68}
    for col, width in widths.items():
        detail.column_dimensions[col].width = width
    detail.freeze_panes = 'D6'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name('dashboard.' + uuid.uuid4().hex + '.xlsx')
    wb.save(temporary)
    # Verify the saved file before replacing the user's dashboard.
    check = load_workbook(temporary, read_only=True)
    if check.sheetnames != ['Dashboard', 'Deliverables']:
        raise ValueError('Workbook validation failed; prior dashboard preserved')
    check.close()
    os.replace(temporary, destination)
