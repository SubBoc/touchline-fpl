"""Protect common unambiguous period phrases; ambiguous requests stay with the model."""
import re

WORDS=dict(zip(('one two three four five six seven eight nine ten eleven twelve '
    'thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty').split(),range(1,21)))
for tens,base in (('twenty',20),('thirty',30)):
    WORDS[tens]=base
    for name,number in list(WORDS.items()):
        if number<10 and base+number<=38:
            WORDS[tens+'-'+name]=base+number
TOKEN=r'\d+|'+'|'.join(re.escape(x) for x in sorted(WORDS,key=len,reverse=True))
UNIT=r'(?:game\s*weeks?|gws?)'


def requested_interval(prompt,first,last):
    text=prompt.casefold().replace('–','-').replace('—','-')
    intervals=set()
    for direction,number in re.findall(r'\b(first|last)\s+('+TOKEN+r')\s*(?:completed\s+)?'+UNIT,text):
        count=int(number) if number.isdigit() else WORDS[number]
        intervals.add((first,first+count-1) if direction=='first' else (last-count+1,last))
    for start,end in re.findall(UNIT+r'\s*(\d+)\s*(?:-|to|through)\s*(?:'+UNIT+r'\s*)?(\d+)',text):
        intervals.add((int(start),int(end)))
    for end in re.findall(r'up to(?:\s+and including)?\s*'+UNIT+r'\s*(\d+)',text):
        intervals.add((first,int(end)))
    if (not intervals and re.search(r'\bseason\b',text) and
            (re.search(r'\b(?:entire|full|whole)\b',text) or
             not re.search(r'\b(?:first|last|recent|past|previous|next|upcoming|form)\b',text))):
        intervals.add((first,last))
    return next(iter(intervals)) if len(intervals)==1 else None
