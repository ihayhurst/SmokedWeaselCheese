from ldap3 import Server, Connection, ALL, NTLM, Tls
import ssl,sys
import config
import functools
import json

class AD:

    def __init__(self, region = 'EAME'):
        '''  Region not used in setting base as using port 3268 gives global catalog '''
        self.region = region
        AD.set_base(self, self.region)

    def set_base(self, region):
        self.search_base = ldap_base
        print(self.search_base)

    def get_base(self):
        print(self.search_base)

    @functools.lru_cache(maxsize=128, typed=False)
    def fetch(self, search_filter, attributes):
        with Connection(server, ldap_user, ldap_pass) as conn:
            conn.search(self.search_base, search_filter, search_scope='SUBTREE', attributes=attributes)
            entry = conn.entries[0].entry_to_json()

            return(entry)

    def user(self, username):
        search_filter = f'(sAMAccountName={username})'
        attributes = ['givenName', 'sn',  'samaccountname', 'displayName', 'mail' ]
        return AD.fetch(self, search_filter, attributes)

    def thumbnail(self, username):
        search_filter = f'(sAMAccountName={username})'
        attributes = ['thumbnailPhoto']
        return AD.fetch(self, search_filter, attributes)

    def user_from_mail(self, mail):
        search_filter = f'(mail={mail})'
        attributes = ['givenName', 'sn',  'samaccountname', 'displayName' ]
        return AD.fetch(self, search_filter, attributes)

    def extract_thumbnail(self, username):
        image  = AD.thumbnail(self, username)
        lookup = json.loads(image)
        return (lookup["attributes"]["thumbnailPhoto"][0]["encoded"])


ldap_server = config.ldap_server
ldap_port = config.ldap_port
ldap_user = config.ldap_user
ldap_pass = config.ldap_pass
ldap_base = config.ldap_base
server = Server(ldap_server, port=ldap_port,  use_ssl=False, get_info=ALL)
tls_configuration = Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLSv1)
conn = Connection(server, ldap_user, ldap_pass, authentication=NTLM, auto_bind=True, client_strategy='REUSABLE')
context=ssl.create_default_context()


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError:
        print("Give me something to do")
        sys.exit(1)
