import tarfile
import email.parser
import email.utils
import dateutil.parser
import sys
import uuid
import json
import re

class email_name(str):
    """
    An object initialized with a string that should be
    an e-mail address: performs operations to parse out
    the names and addresses associated.
    """

    def split(self):
        return email.utils.parseaddr(self)
    
    def elements(self):
        """
        Returns a dictionary with, where possible, the
        - name
        - address
        - username (address before the @)
        - domain (address after the @)
           - top-level domain
           - mid-level domain (oxford.ac.uk, berkeley.edu)
        of the initialized e-mail.
        """
        elements = dict()
        try:
            splat = self.split()
            elements['name'] = splat[0]
            elements['address'] = splat[1].lower()
        except IndexError:
            pass
        try:
            splitName = elements['address'].split("@")
            elements['username'] = splitName[0].lower()
            elements['domain'] = splitName[1].lower()
            domains = list(reversed(elements['domain'].split(".")))
            elements["tld"] = domains[0]
            # mid-level domains are things like 'ge.com' or 'nasa.gov'
            elements["mld"] = ".".join(list(reversed(domains[:2])))
            try:
                # The 'oxford.ac.uk' exception
                if domains[1] in ["ac","edu","co","com","gov","oz"]:
                    elements["mld"] = ".".join(list(reversed(domains[:3])))
            except IndexError:
                pass
        except IndexError:
            pass
        return elements

# Create just once for speed.
parser = email.parser.Parser()

class email_message(object):
    def __init__(self,string,id=None):
        """
        Initializes with an e-mail string and, optionally, a parser.
        (Operations will be faster if you don't create the parser anew each time.
        """
        global parser
        self.string = string
        try:
            self.parsed = parser.parsestr(string)
        except UnicodeEncodeError:
            raise
            
        # Creating a uuid a little early.
        # THIS ALWAYS FAILS. EVERY UUID IS THE SAME. WHY????

        if id is None:
            self.uuid = uuid.uuid1()
            self.uuid = self.uuid.hex
        else:
            self.uuid=id

    def metadata(self,additional_keys = dict(),yearlims=[1970,2020]):
        """
        Return metadata as a dictionary for the object.

        Optionally initialized with a dict of elements to be included,
        including the unique id as 'filename'.
        
        "yearlims" is an array of bounding years. Any years outside this 
        indicate a date-parsing error, and are dropped.
        """
        metadata = dict(self.parsed)

        # Get the ID and other fields from additional_keys
        if 'filename' not in additional_keys:
            additional_keys['filename'] = self.uuid

        for key,value in additional_keys.items():
            metadata[key] = value

        metadata['searchstring'] = self.string.replace("\n","<br>").replace("\t","     ")

        if "From" in metadata:
            email = email_name(metadata["From"])
            emailFields = email.elements()
            for key in emailFields.keys():
                metadata["sender_" + key] = emailFields[key]

        try: 
            metadata["date"] = dateutil.parser.parse(metadata["Date"]).isoformat()
            year = metadata["date"][:4]
            if int(year) < yearlims[0] or int(year) > yearlims[1]:
                year = ""
        except:
            pass

        return metadata


    def write_to_files(self,catalog,input):
        """
        Writes the email out to the specified jsoncatalog.txt and input.txt files,
        which should be writable filehandles.

        Returns true.
        """



        metadata = self.metadata({'filename':self.uuid})
        catalog.write(json.dumps(metadata) + "\n")
        text = self.parsed.get_payload().replace("\n","\\n\\n").replace("\t"," ")
        input.write(metadata['filename'] + "\t" + text.encode("utf-8","ignore") + "\n")


def blocks_of_text(file):
    """
    Breaks a text into white-space separated blocks.
    Some will be kept, some dropped.
    """
    text = ""
    for line in file:
        line = line.replace("\r","\n").replace("\n\n","\n")
        if line=="\n":
            if text != "\n":
                #Don't just return a previously blank line
                yield text
            text = ""
        else:
            text += line
    yield text


def archive_to_emails(filename):
    """
    Initialized with a filename: yields a succession of email objects, hopefully.
    """
    lastBlank = True
    text = ""

    file = open(filename)


    def yield_up(text):
        """
        A little wrapper to handle IDs and error handling.
        """
        try:
            return email_message(text,uuid.uuid1().hex)
        except UnicodeError:
            pass
                    
    for block in blocks_of_text(file):
        block= block.decode("utf-8","ignore")

        skipOn = False
        # Just skip the whole block for these regexes        
        for regex in [r"^From humanist-bounces" # Humanist headers
                      , r"                  Humanist Discussion Group, Vol."
                      , r"^  \[[0-9]+\]  From:    " # A table of contents format
                  ]:
            if re.search(regex,block):
                # Continuing from inside a for-loop breaks the wrong level.
                skipOn = True
        
        if skipOn:
            continue
                
        #Signals start of a block
        if block.startswith("From: "):
            yield yield_up(text)
            text = block
            
        # Humanist Format
        elif re.search(r"^(--\[[0-9]+\]------------+\n)?        Date:",block):
            yield yield_up(text)
            lines = block.split("\n")
            lines = [re.sub("^ +","",line) for line in lines if re.search("^ +",line)]
            text = "\n".join(lines) + "\n"

        # else just keep on going
        # Add in one extra newline
        else:
            text = text + "\n" + block

    # Yield one last time at the end.
    yield yield_up(text)
