import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from lemmatization_claim_audit.audit import audit, evidence, matches, prose
from lemmatization_claim_audit.phrases import LEMMA, NOLEMMA, GENERIC_NAMES

ROOT = Path(__file__).resolve().parents[1]

class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        self.assertEqual(LEMMA, ['lemmatization', 'lemmatizer', 'lemmatizes', 'lemmatize', 'lemmatizes text', 'lemmatize text', 'lemmatizes words', 'lemmatize words', 'lemmatizes tokens', 'lemmatize tokens', 'word lemmatization', 'lemmatization support', 'lemmatizer support', 'supports lemmatization', 'provides lemmatization', 'performs lemmatization', 'lemmatization feature', 'lemmatization capability', 'lemmatization system', 'lemmatization model', 'supports a lemmatizer', 'provides a lemmatizer', 'lemmatizes input', 'lemmatize input', 'lemmatizes the text', 'lemmatize the text', 'lemmatizes the input', 'lemmatize the input', 'reduces words to base form', 'reduce words to base form', 'reduces tokens to base form', 'reduce tokens to base form', 'converts words to base form', 'convert words to base form', 'converts tokens to lemmas', 'convert tokens to lemmas', 'text lemmatization', 'text lemmatizer', 'lemmatization pipeline', 'lemmatization step', 'lemmatization process', 'lemmatizes documents', 'lemmatize documents', 'document lemmatization', 'base form', 'base forms', 'wordnet lemmatizer', 'wordnet lemmatization', 'lemma form', 'lemma forms'])
        self.assertEqual(NOLEMMA, ['does not lemmatize', 'do not lemmatize', "doesn't lemmatize", "don't lemmatize", 'no lemmatization', 'without lemmatization', 'never lemmatizes', 'does not perform lemmatization', 'never performs lemmatization', 'lemmatization not supported', 'lemmatization unsupported', 'no lemmatization support', 'lacks lemmatization', 'missing lemmatization', 'lemmatization disabled', 'no lemmatizer', 'without a lemmatizer', 'does not provide lemmatization', 'does not support lemmatization', 'no word lemmatization', 'without lemmatization support', 'does not lemmatize text', 'lemmatization not available', 'no text lemmatization'])
    def test_generic_oracle(self):
        self.assertEqual(GENERIC_NAMES, ['lemmatize', 'lemmatize_text', 'lemmatize_word', 'lemmatize_words', 'lemmatize_sentence', 'lemmatize_sentences', 'lemmatize_document', 'lemmatize_documents', 'lemmatize_input', 'lemmatize_token', 'lemmatize_tokens', 'lemmatize_corpus', 'lemmatize_paragraph', 'lemmatize_line', 'lemmatize_lines', 'get_lemma', 'get_lemmas', 'get_base_form', 'to_lemma', 'to_base_form', 'word_lemmatize', 'sentence_lemmatize', 'text_lemmatize', 'reduce_to_lemma'])

    def test_generic_forms(self):
        for name in GENERIC_NAMES:
            for source in ['obj.' + name + '(text)', 'from vendor import ' + name + '\n' + name + '(text)', 'from vendor import ' + name + ' as f\nf(text)']:
                with self.subTest(source=source):
                    self.assertTrue(evidence(source))

    def test_span_removal(self):
        denied, rest = matches('does not lemmatize', NOLEMMA)
        self.assertEqual(denied, ['does not lemmatize'])
        self.assertEqual(matches(rest, LEMMA)[0], [])

    def test_longest_first(self):
        self.assertEqual(matches('lemmatization system', LEMMA)[0], ['lemmatization system'])

    def test_fences(self):
        self.assertEqual(matches(prose('```text\nlemmatization\n```'), LEMMA)[0], [])

    def test_inline(self):
        self.assertEqual(matches(prose('`lemmatization`'), LEMMA)[0], ['lemmatization'])

    def test_all_phrases(self):
        for phrase in LEMMA:
            self.assertEqual(len(matches(phrase.upper(), [p.upper() for p in LEMMA])[0]), 1)
        for phrase in NOLEMMA:
            _, remaining = matches(phrase, NOLEMMA)
            self.assertEqual(matches(remaining, LEMMA)[0], [])

    def fixture(self, prose_text, source='', rel='README.md'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prose_text)
        (root / 'app.py').write_text(source)
        return root

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'lemmatization_claim_audit', *map(str, args)], capture_output=True, text=True, cwd=ROOT)

    def test_cli_good(self):
        result = self.cli('audit', self.fixture('lemmatization', 'token.lemma_'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'PASS')

    def test_cli_bad(self):
        root = self.fixture('lemmatization')
        result = self.cli('audit', root, '--json')
        self.assertEqual(result.returncode, 2)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual((data[0]['id'], data[0]['severity']), ('documented-lemmatization-claim-false', 'HIGH'))
        self.assertEqual(data[0]['verdict'], 'FAIL')
        self.assertTrue(data[0]['message'])

    def test_cli_denial(self):
        result = self.cli('audit', self.fixture('does not lemmatize', 'token.lemma'), '--json')
        self.assertEqual(result.returncode, 2)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual((data[0]['id'], data[0]['severity']), ('documented-no-lemmatization-claim-false', 'HIGH'))

    def test_cli_test_only(self):
        root = self.fixture('lemmatization', rel='tests/fixtures/README.md')
        self.assertEqual(self.cli('audit', root).returncode, 0)
        result = self.cli('audit', root, '--fail-on', 'medium', '--json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)[0]['severity'], 'MEDIUM')

    def test_cli_no_claim(self):
        self.assertEqual(self.cli('audit', self.fixture('Hello world')).stdout.strip(), 'PASS')

    def test_cli_version(self):
        result = self.cli('--version')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '0.1.0')

    def test_cli_ignore(self):
        self.assertEqual(self.cli('audit', self.fixture('lemmatization'), '--ignore', 'README').stdout.strip(), 'PASS')

    def test_cli_verbose(self):
        result = self.cli('audit', self.fixture('Hello'), '--verbose')
        self.assertIn('Scope:', result.stderr)
        self.assertIn('SCAN README.md', result.stderr)

    def test_cli_errors(self):
        self.assertEqual(self.cli('audit', '/nonexistent/lca').returncode, 1)
        self.assertEqual(self.cli('audit', '--unknown').returncode, 1)

    def test_self_audit(self):
        self.assertEqual(matches(prose((ROOT / 'README.md').read_text()), LEMMA)[0], [])
        self.assertEqual(matches(prose((ROOT / 'README.md').read_text()), NOLEMMA)[0], [])
        self.assertEqual(audit(ROOT), [])

    def test_split_modules(self):
        root = self.fixture('lemmatization', 'from nltk.stem import WordNetLemmatizer\nx=WordNetLemmatizer()')
        (root / 'other.py').write_text('from app import x\nx.lemmatize("words")')
        # A generic imported instance would otherwise bypass the required pair.
        self.assertEqual(len(audit(root)), 1)

    def test_exclusions(self):
        root = self.fixture('lemmatization')
        for directory in ['.git', '__pycache__', '.venv', 'custom']:
            folder = root / directory
            folder.mkdir()
            (folder / 'evidence.py').write_text('token.lemma_')
            if directory == 'custom':
                (folder / 'pyvenv.cfg').write_text('home = /tmp')
        self.assertEqual(len(audit(root)), 1)


POSITIVE = [
 'import nltk\nx=nltk.WordNetLemmatizer()\nx.lemmatize("x")',
 'import nltk as nk\nnk.WordNetLemmatizer().lemmatize("x")',
 'from nltk.stem import WordNetLemmatizer as W\nx=W()\nx.lemmatize("x")',
 'from nltk.stem.wordnet import WordNetLemmatizer\nWordNetLemmatizer().lemmatize("x")',
 'token.lemma_', 'word.lemma',
 'import nltk\nnltk.lemmatize("x")',
 'import stanza\nstanza.lemmatize_text("x")',
 'import spacy_lemmatizer as sl\nf=sl.Lemmatizer()\nf("x")',
 'from spacy_lemmatizer import Lemmatizer as L\nL()("x")',
 'import spacy_lemmatizer\nspacy_lemmatizer.Lemmatizer()("x")',
 'import stanza\np=stanza.Pipeline(processors="tokenize,lemma")\np("x").sentences[0].words[0].lemma',
 'from stanza import Pipeline as P\nP(processors="lemma")("x").lemma',
 'import lemminflect\nlemminflect.getLemma("x")',
 'import lemminflect as li\nli.getLemma("x")',
 'from lemminflect import getLemma as g\ng("x")',
 'import simplemma\nsimplemma.text_lemmatizer("x")',
 'import simplemma as sm\nsm.text_lemmatizer("x")',
 'from simplemma import text_lemmatizer as t\nt("x")',
]
NEGATIVE = [
 'import nltk, stanza, simplemma, lemminflect, spacy_lemmatizer',
 'from nltk.stem import WordNetLemmatizer',
 'from vendor import lemmatize',
 'from nltk.stem import PorterStemmer\nPorterStemmer().stem("running")',
 'from nltk.stem import LancasterStemmer\nLancasterStemmer().stem("running")',
 'from nltk.stem import SnowballStemmer\nSnowballStemmer("english").stem("running")',
 'obj.stem("x")',
 'from nltk import word_tokenize\nword_tokenize("x")',
 'obj.tokenize("x")', 'Tokenizer()("x")',
 'from nltk import pos_tag\npos_tag([])', 'token.pos_\ntoken.tag_',
 'from nltk import ne_chunk\nne_chunk([])', 'doc.ents',
 'pipeline("ner")', 'tagger=NERTagger()\ntagger.predict("x")',
 'token.dep_\ntoken.head', 'DependencyParser()("x")',
 'p=ConstituencyParser()\np.parse("x")', 'from nltk import Tree\nTree.fromstring("(S x)")',
 'from nltk.corpus import stopwords\nstopwords.words("english")', 'remove_stopwords("x")',
 'from nltk.stem import WordNetLemmatizer\nx=WordNetLemmatizer()',
 'from spacy_lemmatizer import Lemmatizer\nx=Lemmatizer()',
 'import stanza\nstanza.Pipeline(processors="tokenize")',
 'import stanza\nstanza.Pipeline(processors="lemma")',
 'import spacy\nspacy.load("en")',
 '"lemma lemmatize"\n# lemmatize\n', 'lemmatize',
 'def lemmatize(x): return x\nlemmatize("x")',
 'from vendor import lemmatize\ndef lemmatize(x): return x\nlemmatize("x")',
 'from vendor import lemmatize as f\ndef f(x): return x\nf("x")',
 'from nltk.stem import WordNetLemmatizer\nclass WordNetLemmatizer: pass\nx=WordNetLemmatizer()\nx.lemmatize("x")',
 'from spacy_lemmatizer import Lemmatizer\nclass Lemmatizer: pass\nx=Lemmatizer()\nx("x")',
 'import nltk as nk\nclass WordNetLemmatizer: pass\nx=nk.WordNetLemmatizer()\nx.lemmatize("x")',
 'import subprocess\nsubprocess.run(["lemmatize", "file"])',
]


def make_case(source, expected):
    def test(self):
        self.assertEqual(evidence(source), expected, source)
    return test


for index, source in enumerate(POSITIVE):
    setattr(AuditTests, 'test_evidence_positive_%02d' % index, make_case(source, True))
for index, source in enumerate(NEGATIVE):
    setattr(AuditTests, 'test_evidence_rejection_%02d' % index, make_case(source, False))

if __name__ == '__main__':
    unittest.main()
