#!/usr/bin/python3

# *** USEFUL FUNCTIONS ***
import re, argparse

def parse_args(s, num_optional=None, num_mandatory=None):
    saved_groups = []
        
    level        = 0
    read_chars   = 0
    mandatory_ix = 0

    for cndx, c in enumerate(s):
        read_chars += 1
        if level == 0: 
            if c == ' ':
                continue
            elif c not in '[{':
                c_mand = len([g for gtype, g in saved_groups if gtype=='{'])
                if c_mand == num_mandatory:
                    read_chars -= 1
                    break
                else:
                    # Single character mandatory group
                    saved_groups.append( ('{', c) )

            elif c in '[{':
                if num_optional is not None and num_mandatory is not None and \
                   (num_optional+num_mandatory) == len(saved_groups):
                    read_chars -= 1
                    break
                    
                group_type = c
                level = 1
                cur_group = ""
            
            else:
                raise Exception(s, c)
                
        elif c in '[{':
            if c == group_type:
                level += 1
            cur_group += c

        elif (c==']' and group_type =='[') or (c=='}' and group_type=='{'):
            if level == 1:
                saved_groups.append( (group_type, cur_group) )
                    
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
     
    saved_groups, _  = parse_args(v.group('definition'))

    macroname = v.group('macroname')

    mandatory_args = [g for group_type, g in saved_groups if group_type == '{']
    optional_args  = [g for group_type, g in saved_groups if group_type == '[']
    assert(len(mandatory_args)==1)
    for gndx, (group_type, g) in enumerate(saved_groups):
        for group_type2, g2 in saved_groups[gndx:]:
            if group_type == '{' and group_type2 == '[':
                raise Exception("Parsing error: optional arguments must precede mandatory ones.")


    if len(optional_args):
        num_args = int(optional_args[0])
        if len(optional_args) > num_args+1:
            raise Exception(macroname)
            
        argdefs = optional_args[1:]
        argdefs += [None,]*(num_args-len(argdefs))
    else:
        argdefs = None

    return macroname, argdefs, mandatory_args[0]


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
            num_mandatory  = len([a for a in argdefs if a is None])
            num_optional   = len([a for a in argdefs if a is not None])
            saved_groups, readchars  = parse_args(rest_of_string, 
                                                  num_optional=num_optional, 
                                                  num_mandatory=num_mandatory)

            
            newV = macrosub
            parsed_num = 0
            for argnum, defval in enumerate(argdefs):
                if defval is not None: # optional argument in definition
                    if len(saved_groups) > parsed_num and saved_groups[parsed_num][0] == '[': 
                        # parsed optional argument
                        cur_param_value = saved_groups[parsed_num][1]
                        parsed_num += 1
                    else:
                        cur_param_value = defval
                else: # mandatory argument in definition
                    if saved_groups[parsed_num][0] != '{': # didn't parsed mandatory argument
                        raise Exception()
                    else:
                        cur_param_value = saved_groups[parsed_num][1]
                        parsed_num += 1
                            
                newV = newV.replace('#%d'%(argnum+1), ' '+cur_param_value+' ')
                
            num_replacements += 1

            s = s[:result.start()]+" "+newV+" "+rest_of_string[readchars:]
            
    return s, num_replacements

import argparse
import os.path
print_pfx = r"# demacro-lyx:"

parser = argparse.ArgumentParser(description='Remove macros from LyX file')
parser.add_argument('-f', action='store_true', help='Overwrite output file if it exists')
parser.add_argument('input_file', type=str, help='Source .lyx file')
parser.add_argument('output_file', type=str, help='Target .lyx file', nargs='?', default=None)

args = parser.parse_args()

if not os.path.exists(args.input_file):
	raise Exception("Input file %s doesn't exist" % args.input_file)

if args.output_file is not None and os.path.exists(args.output_file):
    if not args.f:
    	raise Exception("Output file %s already exists, don't want to overwrite. Pass -f flag to overwrite" 
            % args.output_file)
    else:
        print(print_pfx, "Output file %s already exists, overwriting" % args.output_file)


# **** READ IN FILE ***

in_macro   = False
in_note_inset_depth = 0
new_content = []
macros = {}

with open(args.input_file, "r") as f:
    for line in f.readlines():
        l = line.strip()
        if in_note_inset_depth > 0:
            if l.startswith("\\begin_inset "):  
                in_note_inset_depth += 1
            elif line.strip() == "\\end_inset":
                in_note_inset_depth -= 1

        elif l == "\\begin_inset Note Note":  # We remove notes
            in_note_inset_depth += 1

        elif l == "\\begin_inset FormulaMacro":
            in_macro       = True
            skip_macro     = False
            current_block  = line

        elif in_macro:
            current_block += line
            if l.startswith("\\newcommand{"):
                macroname, argdefs, macrodef = parse_macrodef(l)
                macros[macroname] = (argdefs, macrodef)
                    
            elif l.startswith("\\renewcommand{"):
                raise Exception("Redefined macros are not supported. Please make that each macro is defined only once.\n%s"% l)

            elif l == "\\end_inset":
                in_macro = False

            else:
                raise Exception("Unknown command: %s" % l)
        
        else:
            new_content += line

base_content = "".join(new_content)

# *** DO REPLACEMENTS ****

s = base_content

while True:
    print(print_pfx, "*** Doing another round of replacements ***")
    changed_in_this_round = False
 
    while True:
        s, num_replacements1 = do_argmacrosubs(s, macros)
        print(print_pfx, "Replaced", num_replacements1)
        if num_replacements1 == 0:
            break
        else:
            changed_in_this_round = True

    while True:
        num_replacements2 = 0
        for macroname, (argdefs, macrosub) in macros.items():
            if argdefs is None or len(argdefs) == 0: # no arguments
                newV = " " + macrosub.replace("\\","\\\\") + " "
                (s,n) = re.subn(re.escape(macroname) + "(?![A-Za-z])", newV, s)
                num_replacements2 += n
        print(print_pfx, "Replaced", num_replacements2)
        if num_replacements2 == 0:
            break
        else:
            changed_in_this_round = True
    
    if not changed_in_this_round:
        break

# *** SAVE or PRINT ***

if args.output_file is not None:
    with open(args.output_file, "w") as f:
    	f.write(s)
    	print(print_pfx, "Written output to %s" % args.output_file)
else:
    print(s)
