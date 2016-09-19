import datetime
import os
here = os.path.dirname(os.path.realpath(__file__))
python_files = []
for root, dirnames, filenames in os.walk(here):
    for f in filenames:
        if f.endswith('.py'):
            python_files.append(os.path.join(root, f))
this_year = datetime.datetime.now().year
for file_path in python_files:
    lines = []
    with open(file_path) as f:
        for l in f:
            if l.startswith('# Copyright ') and 'Joel Dunham' in l:
                new_line = '# Copyright %d Joel Dunham\n' % this_year
                lines.append(new_line)
            else:
                lines.append(l)
    with open(file_path, 'w') as f:
        f.write(''.join(lines))
