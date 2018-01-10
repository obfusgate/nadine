from __future__ import unicode_literals

from django.db.models import Q
from django.core.management.base import BaseCommand, CommandError

from nadine.models import User
from nadine_ldap.models import LDAPAccountStatus
from nadine_ldap.ldap import get_ldap_account_safely, update_ldap_account, delete_ldap_account

class Command(BaseCommand):
    """
    Command to synchronize user accounts into a configured LDAP instance.
    """

    help = """
        Synchronizes user accounts into a configured LDAP instance. By default
        it will only attempt to update accounts that either haven't been
        synchronized or have failed.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '-u', '--user-id',
            help="A specific user id to synchronize. For multiple specific users pass argument multiple times",
            action='append',
            type=int,
        )
        parser.add_argument(
            '-n', '--user-name',
            help="A specific user name to synchronize. For multiple specific users pass argument multiple times",
            action='append',
        )
        parser.add_argument(
            '-f', '--force',
            help="Attempt to synchronize all user accounts instead of just those that haven't been synchronized or failed",
            action='store_true',
            default=False,
        )

    def handle(self, *args, **options):
        query = {}
        if options['user_id']:
            query['pk__in'] = options['user_id']
        if options['user_name']:
            query['username__in'] = options['user_name']

        if not options['force']:
            query['ldapaccountstatus__synchronized'] = False

        users = User.objects.filter(**query)
        self.sync_users(users)
        self.clean_up_accounts()

    def sync_users(self, users):
        if users:
            total = len(users)
            successful = 0
            failed = 0

            self.stdout.write("Attempting to synchronize {} accounts to LDAP".format(total))
            for user in users:
                self.stdout.write("Synchronizing '{}({})'...".format(user, user.id), ending='')
                update_ldap_account(user, create=True)
                ldap_account = get_ldap_account_safely(user)
                
                if ldap_account.synchronized:
                    self.stdout.write(self.style.SUCCESS(' Success!'))
                    successful = successful + 1
                else:
                    self.stdout.write(self.style.ERROR(' Error'))
                    self.stdout.write(self.style.NOTICE(ldap_account.ldap_error_message))
                    failed = failed + 1
            self.stdout.write("{}/{} accounts synchronized to LDAP, {} failures".format(successful, total, failed))

        else:
            self.stdout.write("No accounts synchronized, to force synchronization use the 'force' argument")

    def clean_up_accounts(self):
        to_delete = LDAPAccountStatus.objects.filter(user=None)
        for ldap_account in to_delete:
            self.stdout.write("Deleting account '{} ({})'...".format(ldap_account.dn, ldap_account.cn))
            delete_ldap_account(ldap_account)
