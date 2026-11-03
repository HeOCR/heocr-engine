"""Create public-authored disjoint text groups and local font manifests."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def corpora():
    train = [f'{a} {b} {c}.' for a in ['הוועדה בדקה', 'המשרד אישר', 'הצוות בחן', 'הממונה קיבל', 'המערכת שמרה', 'המזכירות הכינה', 'המחלקה רשמה', 'היחידה העבירה'] for b in ['את הטופס', 'את המסמך', 'את הבקשה', 'את התיק', 'את הרישום', 'את האישור', 'את הדוח', 'את ההודעה'] for c in ['בשלב הראשון', 'לאחר בדיקה']]
    val = [f'{a} {b} {c}.' for a in ['הנהלת הפרויקט', 'נציגי השירות', 'חברי המועצה', 'עורכי המסמך'] for b in ['עדכנו את הרשימה', 'סיכמו את הדיון', 'שמרו את הנוסח', 'בדקו את התשובה'] for c in ['בשעות הבוקר', 'לקראת הפגישה']]
    test = [f'{a} {b} {c}.' for a in ['המסגרת הציבורית', 'ועדת הבחינה', 'צוות האיכות', 'מנהלת התוכנית'] for b in ['פרסמה הנחיות', 'החזירה הערות', 'שלחה תזכורת', 'קבעה סדרי עבודה'] for c in ['לקראת המועד', 'בהתאם להחלטה']]
    return {'train': train, 'validation': val, 'test': test}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--alef-font', type=Path, required=True)
    parser.add_argument('--noto-font', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / 'inputs'
    fonts = inputs / 'fonts'
    fonts.mkdir(parents=True)
    for key, value in corpora().items():
        (inputs / f'{key}.txt').write_text('\n'.join(value) + '\n', encoding='utf-8')
    for name, source in [('alef', args.alef_font), ('noto', args.noto_font)]:
        shutil.copyfile(source, fonts / f'{name}.ttf')
        font_id = 'alef-regular' if name == 'alef' else 'noto-sans-hebrew'
        (fonts / f'{name}.yaml').write_text(f'fonts:\n  - id: {font_id}\n    file: {name}.ttf\n    style: printed\n')
    hashes = {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs.rglob('*') if f.is_file()}
    (inputs / 'input-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')


if __name__ == '__main__':
    main()
