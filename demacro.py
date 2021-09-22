#!/usr/bin/python3

# *** USEFUL FUNCTIONS ***
import re, argparse

def parse_args(s, max_groups = None, break_on_nonbracket=False, separate_bracket_types=True):
    if separate_bracket_types:
        saved_groups = {'{':[],'[':[]}
    else:
        saved_groups = []
        
    level = 0
    read_chars = 0
    for c in s.strip():
        read_chars += 1
        if level == 0: 
            if c == ' ':
                continue
            elif c not in '[{' and break_on_nonbracket:
                read_chars -= 1
                break
            elif c in '[{':
                if max_groups == sum(map(len, saved_groups)):
                    read_chars -= 1
                    break
                    
                in_group = c
                level = 1
                cur_group = ""
            
            else:
                raise Exception(s, c)
                
        elif c in '[{':
            if c == in_group:
                level += 1
            cur_group += c

        elif (c==']' and in_group =='[') or (c=='}' and in_group=='{'):
            if level == 1:
                if separate_bracket_types:
                    saved_groups[in_group].append(cur_group)
                else:
                    saved_groups.append(cur_group)
                    
            else:
                cur_group += c
            level -= 1
            
        else:
            cur_group += c
            
    return saved_groups, read_chars
    
def parse_macrodef(s):
    s = s.strip()
    pattern = r"\\newcommand{(?P<macroname>[\\A-Za-z]+)}\w*(?P<definition>.+)"

    v=re.match(pattern, s)
    
    if v is None:
        print(s)
        raise Exception()
     
    saved_groups, _ =parse_args(v.group('definition'))
    
    macroname = v.group('macroname')
    assert(len(saved_groups['{'])==1)
    if len(saved_groups['[']):
        num_args = int(saved_groups['['][0])
        if len(saved_groups['[']) > num_args+1:
            raise Exception(macroname)
            
        argdefs = saved_groups['['][1:]
        argdefs += [None,]*(num_args-len(argdefs))
    else:
        argdefs = None
        
    return macroname, argdefs, saved_groups['{'][0]


def do_argmacrosubs(s, macros):
    num_replacements = 0
    for macroname, (argdefs, macrosub) in macros.items():
        if argdefs is None or len(argdefs) == 0: # no arguments
            continue
            
        while True:
            result = re.search(re.escape(macroname)+"(?![A-Za-z])", s)
            if result is None:
                break
            
            rest_of_string = s[result.start()+len(macroname):]
            v, readchars=parse_args(rest_of_string, break_on_nonbracket=True, separate_bracket_types=False)
            
            newV = macrosub
            for argnum in range(len(argdefs)):
                if len(v)<=argnum or v[argnum] == "":
                    cur_param_value = argdefs[argnum]
                else:
                    cur_param_value = v[argnum]

                if cur_param_value is None:
                    # sometimes argument to macros with non-optional arguments are not escaped
                    if len(argdefs)==1 and argdefs[0] is None:
                        nextWord = re.search(r"\s*\w+\b", rest_of_string)
                        if nextWord: 
                            cur_param_value = nextWord.group().strip()
                            readchars = len(nextWord.group())
                            
                if cur_param_value is None:
                    print(macroname, argnum)
                    raise Exception()

                newV = newV.replace('#%d'%(argnum+1), ' '+cur_param_value+' ')
                
            num_replacements += 1
            s = s[:result.start()]+" "+newV+" "+rest_of_string[readchars:]
            
    return s, num_replacements


import argparse

parser = argparse.ArgumentParser(description='Remove macros from LyX file')
parser.add_argument('input_file', type=str, help='Source .lyx file')
parser.add_argument('output_file', type=str, help='Target .lyx file')

args = parser.parse_args()

import os.path

if not os.path.exists(args.input_file):
	raise Exception("Input file %s doesn't exist" % args.input_file)

if os.path.exists(args.output_file):
	raise Exception("Output file %s already exists, don't want to overwrite" % args.output_file)


# **** READ IN FILE ***

in_macro   = False
s = "\\newcommand{"
new_content = []
macros = {}

with open(args.input_file, "r") as f:
    for line in f.readlines():
        l = line.strip()
        if l == "\\begin_inset FormulaMacro":
            in_macro = True
            skip_macro = False
            current_block  = line
        elif in_macro:
            current_block += line
            if l.startswith(s):
                macroname, argdefs, macrodef = parse_macrodef(l)
                macros[macroname] = (argdefs, macrodef)
                    
            elif line.strip() == "\\end_inset":
                in_macro = False

            else:
                raise Exception("Unknown command:", l)
        
        else:
            new_content += line

base_content = "".join(new_content)

# *** DO REPLACEMENTS ****

s = base_content

while True:
    changed_in_this_round = False
    
    while True:
        s, num_replacements1 = do_argmacrosubs(s, macros)
        print("Replaced", num_replacements1)
        if num_replacements1 == 0:
            break
        else:
            changed_in_this_round = True

    print()
    while True:
        num_replacements2 = 0
        for macroname, (argdefs, macrosub) in macros.items():
            if argdefs is None or len(argdefs) == 0: # no arguments
                #if macroname == "\\pp":
                #    print(re.escape(macroname) + "(?![A-Za-z])")
                #    print(macrosub)
                newV = " " + macrosub.replace("\\","\\\\") + " "
                (s,n) = re.subn(re.escape(macroname) + "(?![A-Za-z])", newV, s)
            num_replacements2 += n
        print("Replaced", num_replacements2)
        if num_replacements2 == 0:
            break
        else:
            changed_in_this_round = True
    print()
    
    if not changed_in_this_round:
        break

# *** SAVE ***

with open(args.output_file, "w") as f:
	f.write(s)
	print("Written output to %s" % args.output_file)
