from __future__ import unicode_literals

from django.db.utils import Error as DBError

from models import LDAPPosixUser, LDAPAccountStatus

def get_ldap_account_safely(user):
    """
    Safely check if user has an LDAPAccountStatus record.
    If exists, return it, otherwise returns None.
    """
    if hasattr(user, 'ldapaccountstatus'):
        return user.ldapaccountstatus

def get_or_create_ldap_account(user):
    ldap_status, created = LDAPAccountStatus.objects.get_or_create(user=user)
    return ldap_status

def update_ldap_account(user, create=False):
    """
    Attempt to create a user account in LDAP. Log any errors that occur.
    """
    ldap_status = None
    if create:
        ldap_status = get_or_create_ldap_account(user)
    else:
        ldap_status = get_ldap_account_safely(user)

    if not ldap_status:
        return

    user = ldap_status.user
    email_addresses = [address.email for address in user.emailaddress_set.all()]
    try:
        ldap_posix_user, created = LDAPPosixUser.objects.update_or_create(
            nadine_id=str(ldap_status.pk),
            defaults={
                'common_name': user.username,
                'password': user.password,
                'last_name': user.username,
                'email': email_addresses,
            },
        )
        ldap_status.ldap_dn = ldap_posix_user.dn
        clear_ldap_error(ldap_status)

    except DBError as error:
        # Log error and let Django continue as normal.
        log_ldap_error(ldap_status, error)


def delete_ldap_account(ldap_status):
    try:
        ldap_posix_user = LDAPPosixUser.objects.get(nadine_id=str(ldap_status.pk))
        ldap_posix_user.delete()

    except DBError as error:
        log_ldap_error(ldap_status, error)

    except LDAPPosixUser.DoesNotExist:
        # TODO: Passing here as account doesn't appear to exist anyway.
        pass

    # LDAP account has been deleted, it's ok to clean up ldap_status object.
    ldap_status.delete()


def log_ldap_error(ldap_status, error):
    """
    Something went wrong writing to LDAP. Record the problem in Django database
    in a record associated with the user's account.
    """
    ldap_status.synchronized = False
    ldap_status.ldap_error_message = str(error)
    ldap_status.save()


def clear_ldap_error(ldap_status):
    """
    Clears any errors recorded in user's LDAPAccountStatus object.
    Optionally, provide a LDAP dn to be recorded if one exists.
    """
    ldap_status.synchronized = True
    ldap_status.ldap_error_message = ''
    ldap_status.save()
