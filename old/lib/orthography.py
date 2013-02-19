# Copyright 2013 Joel Dunham
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""
Orthography module describes an Orthography class that represents the
orthography of a given language.

OrthographyTranslator facilitates conversion of text in orthography A into
orthography B; takes two Orthography objects at initialization.

This module is adapted and generalized from one written by Patrick Littell
for the conversion of Kwak'wala strings between its many orthographies.

"""

import re


class Orthography:
    """The Orthography class represents an orthography used to transcribe a
    language.
    
    Required as input is a comma-delimited string of graphs.  Graphs are
    represented by strings of one or more unicode characters.  Order of graphs
    is important for sorting words or Forms of the language under study.
    
    Graph variants (allographs?) should be grouped together with brackets.
    
    E.g., orthographyAsString = u'[a,a\u0301],b,c,d'
    
    The above orthography string represents an orthography where u'a' and
    u'a\u0301' are both ranked first, u'b' second, u'c' third, etc.
    
    Idiosyncratic arguments are in **kwargs, e.g.,:
     - lowercase: whether or not the orthography is all-lowercase
     - initialGlottalStops: whether it represents glottal stops (assumed to be
       u'7' in the input orthography) word initially.
       
    """

    def removeAllWhiteSpace(self, string):
        """Remove all spaces, newlines and tabs."""
        string = string.replace('\n', '')
        string = string.replace('\t', '')
        string = string.replace(' ', '') 
        return string
    
    def str2bool(self, string):
        if string == '1':
            return True
        elif string == '0':
            return False
        else:
            return string

    def __init__(self, orthographyAsString, **kwargs):
        """Get core attributes; primarily, the orthography in various datatypes.
        """
        self.orthographyAsString = self.removeAllWhiteSpace(orthographyAsString)
        self.orthographyAsList = self.getOrthographyAsList(
            self.orthographyAsString)
        self.orthographyAsDict = self.getOrthographyAsDict(
            self.orthographyAsString)
        self.lowercase = self.getKwargsArg(kwargs, 'lowercase', True)
        self.initialGlottalStops = self.getKwargsArg(kwargs,
                                                    'initialGlottalStops', True)

    def __repr__(self):
        return 'Orthography Object\n\t%s: %s\n\t%s: %s\n\n%s\n\n%s\n\n%s\n\n' % (
            '# graph types',
            len(self.orthographyAsList),
            '# graphs',
            len(self.orthographyAsDict),
            self.orthographyAsString,
            str(self.orthographyAsList),
            str(self.orthographyAsDict)
        )
        
    def getOrthographyAsList(self, orthography):
        """Returns orthography as a list of lists.

        E.g.,   u'[a,a\u0301],b,c,d'    becomes
                [[u'a',u'a\u0301'],[u'b'],[u'c'],[u'd']]

        """

        inBrackets = False
        result = u''
        for char in orthography:
            if char == u'[':
                inBrackets = True
                char = u''
            elif char == u']':
                inBrackets = False
                char = u''
            if inBrackets and char == u',':
                result += u'|'
            else:
                result += char
        temp = result.split(',')
        result = [item.split('|') for item in temp]
        return result

    def getOrthographyAsDict(self, orthography):
        """Returns orthography as a dictionary of graphs to ranks.
        
        E.g.,   u'[a,a\u0301],b,c,d'    becomes
                {u'a': 0, u'a\u0301': 0, u'b': 1, u'c': 2, u'd': 3}

        """

        inBrackets = False
        result = u''
        for char in orthography:
            if char == u'[':
                inBrackets = True
                char = u''
            elif char == u']':
                inBrackets = False
                char = u''
            if inBrackets and char == u',':
                result += u'|'
            else:
                result += char
        temp = result.split(',')
        result = {}
        for string in temp:
            for x in string.split('|'):
                result[x] = temp.index(string)
        return result

    def getKwargsArg(self, kwargs, key, default=None):
        """Return **kwargs[key] as a boolean, else return default."""
        if key in kwargs:
            return self.str2bool(kwargs[key])
        else:
            return default


class OrthographyTranslator:
    """Takes two Orthography instances and generates a translate method
    for converting strings form the first orthography to the second.
    """

    def __init__(self, inputOrthography, outputOrthography):
        self.inputOrthography = inputOrthography
        self.outputOrthography = outputOrthography

        # If input and output orthography objects are incompatible for
        #  translation, raise an OrthographyCompatibilityError.
        
        if [len(x) for x in self.inputOrthography.orthographyAsList] != \
            [len(x) for x in self.outputOrthography.orthographyAsList]:
            raise OrthographyCompatibilityError()

        self.prepareRegexes()

    def print_(self):
        for key in self.replacements:
            print '%s\t%s' % (key, self.replacements[key])
            
    def getReplacements(self):
        """Create a dictionary with a key for each graph in the input
        orthography; each such key has as value a graph in the output orthography.

        Note: the input orthography may have more than one correspondent in the
        output orthography.  If this is the case, the default is for the system
        to use the first correspondent and ignore all subsequent ones.  This
        means that the order of graphs entered by the user on the Settings page
        may have unintended consequences for translation...
        """

        replacements = {}
        for i in range(len(self.inputOrthography.orthographyAsList)):
            graphTypeList = self.inputOrthography.orthographyAsList[i]
            for j in range(len(graphTypeList)):
                if graphTypeList[j] not in replacements:
                    replacements[graphTypeList[j]] = \
                        self.outputOrthography.orthographyAsList[i][j]
        self.replacements = replacements
        
    def makeReplacementsCaseSensitive(self):
        """Update replacements to contain (programmatically) capitalized inputs
        and outputs.
        
        """

        newReplacements = {}
        for key in self.replacements:
            if not self.isCapital(key):
                capital = self.capitalize(key)
                if capital and capital not in self.replacements:
                    # if output orthography is lc, map uc input orthography
                    #  graphs to lc outputs, otherwise to uc outputs
                    if self.outputOrthography.lowercase:
                        newReplacements[capital] = self.replacements[key]
                    else:
                        newReplacements[capital] = \
                            self.capitalize(self.replacements[key])
        self.replacements.update(newReplacements)

    def prepareRegexes(self):
        """Generate the regular expressions for doing character substitutions
        on the input string that will convert it into the output orthography.
        
        """
        
        # build a dictionary representing the mapping between input and output
        #  orthographies
        
        self.getReplacements()
        
        # 4 Possibilities for .lowercase attribute:
        #  1. io.lc = True, oo.lc = True: do nothing (Default)
        #  2. io.lc = True, oo.lc = False: do nothing (I guess we could
        #   capitalize the first word of sentences, but I'm not gonna right now ...)
        #  3. io.lc = False, oo.lc = True: map lc to lc and uc to lc
        #  4. io.lc = False, oo.lc = False: map lc to lc and uc to uc
        
        if not self.inputOrthography.lowercase:
            self.makeReplacementsCaseSensitive()
        
        # Sort the keys according to length, longest words first, to prevent
        #  parts of n-graphs from being found-n-replaced before the n-graph is.
        
        self.replacementKeys = self.replacements.keys()
        self.replacementKeys.sort(lambda x,y:len(y)-len(x))
        
        # This is the pattern that does most of the work
        #  It matches a string in metalanguage tags ("<ml>" and "</ml>") or
        #  a key from self.replacements
        
        self.regex = re.compile(
            "<ml>.*?</ml>|(" + "|".join(self.replacementKeys) + ")"
        )
        
        # If the output orthography doesn't represent initial glottal stops,
        #  but the input orthography does, compile a regex to remove them from
        #  the input orthography.  That way, the replacement operation won't
        #  create initial glottal stops in the output (Glottal stops are assumed
        #  to be represented by "7".)
        
        if self.inputOrthography.initialGlottalStops and \
            not self.outputOrthography.initialGlottalStops:
            self.initialGlottalStopRemover = re.compile("""( |^|(^| )'|")7""")
    
    # This and the constructor will be the only functions other modules will
    #  need to use;
    #  given a string in the input orthography,
    #  returns the string in the output orthography.
    
    def translate(self, text):
        """Takes text as input and returns it in the output orthography."""
        if self.inputOrthography.lowercase:
            text = self.makeLowercase(text)
        if self.inputOrthography.initialGlottalStops and \
            not self.outputOrthography.initialGlottalStops:
            text = self.initialGlottalStopRemover.sub("\\1", text)
        return self.regex.sub(lambda x:self.getReplacement(x.group()), text)

    # We can't just replace each match from self.regex with its value in
    #  self.replacements, because some matches are metalangauge strings that
    #  should not be altered (except to remove the <ml> tags...)
    
    def getReplacement(self, string):
        """If string DOES NOT begin with "<ml>" and end with "</ml>", then treat
        it as an object language input orthography graph and return
        self.replacements[string].
        
        If string DOES begin with "<ml>" and end with "</ml>", then treat it as 
        a metalanguage string and return it with the "<ml>" and "</ml>" tags.
        """
        if string[:4] == '<ml>' and string[-5:] == '</ml>':
            return string
        else:
            return self.replacements[string]

    # The built-in methods lower(), upper(), isupper(), capitalize(), etc.
    #  don't do exactly what we need here

    def makeLowercase(self, string):
        """Return the string in lowercase except for the substrings enclosed
        in metalanguage tags."""
        patt = re.compile("<ml>.*?</ml>|.")
        def getReplacement(string):
            if string[:4] == '<ml>' and string[-5:] == '</ml>':
                return string
            else:
                return string.lower()
        return patt.sub(lambda x:getReplacement(x.group()), string)

    def capitalize(self, str):
        """If str contains an alpha character, return str with first alpha
        capitalized; else, return empty string.
        """
        result = ""
        for i in range(len(str)):
            if str[i].isalpha(): return str[:i] + str[i:].capitalize()
        return result

    def isCapital(self, str):
        """Returns true only if first alpha character found is uppercase."""
        for char in str:
            if char.isalpha():
                return char.isupper()
        return False


class OrthographyCompatibilityError(Exception):
    def __str__(self):
        return 'An OrthographyTranslator could not be created: the two input ' + \
        'orthographies are incompatible.'


class CustomSorter():
    """Takes an Orthography instance and generates a method for sorting a list
    of Forms according to the order of graphs in the orthography.
    
    """

    def __init__(self, orthography):
        self.orthography = orthography
        
    def removeWhiteSpace(self, word):
        return word.replace(' ', '').lower()

    def getIntegerTuple(self, word):
        """Takes a word and returns a tuple of integers representing the rank of
        each graph in the word.  A list of such tuples can then be quickly
        sorted by a Pythonic list's sort() method.
        
        Since graphs are not necessarily Python characters, we have to replace
        each graph with its rank, starting with the longest graphs first.
        """
        
        graphs = self.orthography.orthographyAsDict.keys()
        graphs.sort(key=len)
        graphs.reverse()
         
        for graph in graphs: 
            word = unicode(word.replace(graph,
                            '%s,' % self.orthography.orthographyAsDict[graph]))

        # Filter out anything that is not a digit or a comma
        word = filter(lambda x: x in '01234546789,', word)
        
        return tuple([int(x) for x in word[:-1].split(',') if x])

    def sort(self, forms):
        """Take a list of OLD Forms and return it sorted according to the order
        of graphs in CustomSorter().orthography.
        """
        temp = [(self.getIntegerTuple(self.removeWhiteSpace(form.transcription)),
                 form) for form in forms]
        temp.sort()
        return [x[1] for x in temp]
        
