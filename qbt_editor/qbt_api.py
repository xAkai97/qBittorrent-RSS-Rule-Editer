"""qBittorrent API helpers.

Contains functions to create a qbittorrent-api client and to sync or fetch
RSS rules. These functions use configuration values from `qbt_editor.config`.
"""
import requests
try:
    from qbittorrentapi import Client, APIConnectionError, Conflict409Error
    _HAVE_QBITTORRENTAPI = True
except Exception:  # ImportError or any other problem while importing the library
    # Provide lightweight placeholders so the module can be imported and
    # tooling (or tests) can run even if qbittorrentapi isn't installed.
    Client = None

    class APIConnectionError(Exception):
        pass

    class Conflict409Error(Exception):
        pass

    _HAVE_QBITTORRENTAPI = False
from . import config
from .utils import create_qbittorrent_rule_def
from tkinter import messagebox
import os


def create_qbittorrent_client(host: str, username: str, password: str, verify_ssl: bool):
    global_config_ca = getattr(config, 'QBT_CA_CERT', None)
    try:
        if global_config_ca:
            try:
                return Client(host=host, username=username, password=password, verify_ssl=global_config_ca if verify_ssl else False)
            except TypeError:
                return Client(host=host, username=username, password=password, verify_ssl=verify_ssl)
        else:
            return Client(host=host, username=username, password=password, verify_ssl=verify_ssl)
    except TypeError:
        client = Client(host=host, username=username, password=password)
        if not verify_ssl:
            try:
                sess = getattr(client, '_http_session', None) or getattr(client, 'http_session', None) or getattr(client, '_session', None) or getattr(client, 'session', None) or getattr(client, 'requests_session', None)
                if sess is not None and hasattr(sess, 'verify'):
                    sess.verify = False
            except Exception:
                pass
        return client


def sync_rules_to_qbittorrent_online(selected_titles, rule_prefix, year, root, status_var):
    if not config.QBT_USER or not config.QBT_PASS or not config.QBT_HOST or not config.QBT_PORT:
        messagebox.showerror("Error", "qBittorrent connection details are missing. Check Settings.")
        return

    full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
    status_var.set(f"Connecting to qBittorrent at {full_host}...")
    root.update()

    try:
        qbt = create_qbittorrent_client(host=full_host, username=config.QBT_USER, password=config.QBT_PASS, verify_ssl=config.QBT_VERIFY_SSL)
        qbt.auth_log_in()
    except APIConnectionError as e:
        messagebox.showerror("Connection Error", f"Failed to connect or authenticate to qBittorrent.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return
    except Exception as e:
        messagebox.showerror("Login Error", f"qBittorrent Login Failed. Check credentials.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return

    try:
        feed_path = "Anime Feeds/" + config.DEFAULT_RSS_FEED.split('//')[1].split('/')[0]
        try:
            qbt.rss_add_feed(url=config.DEFAULT_RSS_FEED, item_path=feed_path)
            qbt.rss_refresh_item(item_path=feed_path)
        except Conflict409Error:
            pass

        successful_rules = 0
        for title in selected_titles:
            sanitized_folder_name = title.replace(':', ' -').replace('/', '_').strip()
            rule_name = f"{rule_prefix} - {sanitized_folder_name}"
            save_path = os.path.join(config.DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}", sanitized_folder_name).replace('\\', '/')
            rule_def = create_qbittorrent_rule_def(rule_pattern=sanitized_folder_name, save_path=save_path, default_rss_feed=config.DEFAULT_RSS_FEED)
            qbt.rss_set_rule(rule_name=rule_name, rule_def=rule_def)
            successful_rules += 1

        messagebox.showinfo("Success (Online)", f"Successfully synchronized {successful_rules} rules to qBittorrent.\n\nAll rules are now active in your remote client.")
        status_var.set(f"Synchronization complete. {successful_rules} rules set.")
    except Exception as e:
        messagebox.showerror("Sync Error", f"An error occurred during rule synchronization: {e}")
        status_var.set("Synchronization failed.")


def test_qbittorrent_connection(protocol_var, host_var, port_var, user_var, pass_var, verify_ssl_var, ca_cert_var=None):
    protocol = protocol_var.get().strip()
    host = host_var.get().strip()
    port = port_var.get().strip()
    user = user_var.get().strip()
    password = pass_var.get().strip()
    verify_ssl = verify_ssl_var.get()

    ca_cert = None
    if ca_cert_var is not None:
        try:
            ca_cert = ca_cert_var.get().strip() or None
        except Exception:
            ca_cert = None
    else:
        ca_cert = getattr(config, 'QBT_CA_CERT', None)

    if not host or not port:
        messagebox.showwarning("Test Failed", "Host and Port cannot be empty.")
        return

    full_host = f"{protocol}://{host}:{port}"

    try:
        verify_arg = ca_cert if (ca_cert and verify_ssl) else verify_ssl
        qbt = create_qbittorrent_client(host=full_host, username=user, password=password, verify_ssl=verify_arg)
        qbt.auth_log_in()
        app_version = qbt.app_version
        messagebox.showinfo("Test Success", f"Successfully connected to qBittorrent!\nProtocol: {protocol.upper()}\nVerification: {'ON' if verify_ssl else 'OFF'}\nVersion: {app_version}")
        return
    except requests.exceptions.SSLError:
        messagebox.showerror("Test Failed", "SSL Error: Certificate verification failed. Try providing a CA cert or unchecking 'Verify SSL Certificate' in settings.")
        return
    except APIConnectionError:
        pass
    except Exception:
        pass

    try:
        session = requests.Session()
        verify_param = ca_cert if (ca_cert and verify_ssl) else verify_ssl

        login_url = f"{full_host}/api/v2/auth/login"
        resp = session.post(login_url, data={"username": user, "password": password}, timeout=10, verify=verify_param)
        if resp.status_code not in (200, 201) or resp.text.strip().lower() not in ('ok.', 'ok'):
            messagebox.showerror("Test Failed", "Login failed. Check Username/Password and try again.")
            return

        version_url = f"{full_host}/api/v2/app/version"
        vresp = session.get(version_url, timeout=10, verify=verify_param)
        if vresp.status_code == 200:
            app_version = vresp.text.strip()
            messagebox.showinfo("Test Success", f"Successfully connected to qBittorrent!\nProtocol: {protocol.upper()}\nVerification: {'ON' if verify_ssl else 'OFF'}\nVersion: {app_version}")
            return
        else:
            messagebox.showerror("Test Failed", "Authenticated but failed to read qBittorrent version. Check permissions.")
            return

    except requests.exceptions.SSLError:
        messagebox.showerror("Test Failed", "SSL Error: Certificate verification failed. Provide a CA cert or disable verification.")
    except requests.exceptions.ConnectionError:
        messagebox.showerror("Test Failed", "Connection refused. Check Host/Port/Protocol and ensure qBittorrent WebUI is running.")
    except Exception as e:
        messagebox.showerror("Test Failed", f"Login or connection error. Check Username/Password.\nDetails: {e}")


def fetch_online_rules(root):
    if not config.QBT_USER or not config.QBT_PASS or not config.QBT_HOST or not config.QBT_PORT:
        messagebox.showerror("Error", "qBittorrent connection details are missing. Check Settings.")
        return None

    full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
    qbt = None
    lib_exc = None
    try:
        qbt = create_qbittorrent_client(host=full_host, username=config.QBT_USER, password=config.QBT_PASS, verify_ssl=config.QBT_VERIFY_SSL)
        qbt.auth_log_in()
        rules_dict = qbt.rss_rules()
        return rules_dict
    except Exception as e:
        lib_exc = e

    try:
        session = requests.Session()
        verify_param = config.QBT_CA_CERT if (getattr(config, 'QBT_CA_CERT', None) and config.QBT_VERIFY_SSL) else config.QBT_VERIFY_SSL

        login_url = f"{full_host}/api/v2/auth/login"
        lresp = session.post(login_url, data={"username": config.QBT_USER, "password": config.QBT_PASS}, timeout=10, verify=verify_param)
        if lresp.status_code not in (200, 201) or lresp.text.strip().lower() not in ('ok.', 'ok'):
            body_snippet = (lresp.text or '')[:300]
            messagebox.showerror("Connection Error", f"Failed to authenticate to qBittorrent. Check credentials.\nHTTP {lresp.status_code}: {body_snippet}")
            return None

        rules_url = f"{full_host}/api/v2/rss/rules"
        rresp = session.get(rules_url, timeout=10, verify=verify_param)
        if rresp.status_code != 200:
            body_snippet = (rresp.text or '')[:300]
            messagebox.showerror("Connection Error", f"Failed to fetch RSS rules: HTTP {rresp.status_code}\n{body_snippet}")
            return None

        data = rresp.json()
        if isinstance(data, dict):
            rules_dict = data
        elif isinstance(data, list):
            rules_dict = {}
            for item in data:
                name = None
                if isinstance(item, dict):
                    name = item.get('ruleName') or item.get('name') or item.get('title') or item.get('rule') or item.get('rule_name')
                if not name:
                    name = str(item)
                rules_dict[name] = item
        else:
            messagebox.showerror("Connection Error", "Unexpected RSS rules response format.")
            return None

        return rules_dict
    except requests.exceptions.SSLError:
        messagebox.showerror("Connection Error", "SSL Error: Certificate verification failed. Try unchecking 'Verify SSL Certificate' in settings or provide CA cert.")
    except requests.exceptions.ConnectionError as e:
        messagebox.showerror("Connection Error", f"Failed to connect to qBittorrent. Check credentials and server status.\nDetails: {e}")
    except Exception as e:
        extra = f"\nLibrary client error: {repr(lib_exc)}" if lib_exc is not None else ""
        messagebox.showerror("Error", f"An unexpected error occurred while fetching RSS rules: {e}{extra}")

    return None


__all__ = [
    'create_qbittorrent_client',
    'sync_rules_to_qbittorrent_online',
    'fetch_online_rules',
    'test_qbittorrent_connection',
]
