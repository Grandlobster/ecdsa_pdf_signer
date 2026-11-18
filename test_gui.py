"""
test_gui.py

Drives the real application window without showing it on screen ("offscreen"),
clicks through every workflow and checks the results.

Run it from the project folder:

    python test_gui.py                 just run the checks
    python test_gui.py screenshots     also save a picture of each screen into ./screenshots

It works in a temporary folder, so your real keys and documents are never touched.
"""

import os
import shutil
import sys
import tempfile

# Test runs use an invisible screen and a throw-away workspace.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
TEST_WORKSPACE = tempfile.mkdtemp(prefix="signet_gui_test_")
os.environ["ECDSA_SIGNER_HOME"] = TEST_WORKSPACE

PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_FOLDER, "backend"))
sys.path.insert(0, os.path.join(PROJECT_FOLDER, "gui"))

from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog

import folders
import identity_storage
import sample_pdf
import theme
import trust_store
import widgets

folders.make_sure_folders_exist()

application = QApplication([])
application.setStyle("Fusion")
application.setFont(theme.make_font("sans", 14))
application.setStyleSheet(theme.GLOBAL_STYLE_SHEET)

from main_window import MainWindow

SCREENSHOT_FOLDER = ""

if len(sys.argv) > 1 and sys.argv[1] == "screenshots":
    SCREENSHOT_FOLDER = os.path.join(PROJECT_FOLDER, "screenshots")
    shutil.rmtree(SCREENSHOT_FOLDER, ignore_errors=True)
    os.makedirs(SCREENSHOT_FOLDER)

STRONG_PASSWORD = "correct-horse-battery-staple"
passed_count = 0
failed_count = 0


def check(description, condition):
    global passed_count
    global failed_count

    if condition:
        passed_count = passed_count + 1
        print("  PASS  " + description)
    else:
        failed_count = failed_count + 1
        print("  FAIL  " + description)


def wait_until(condition_function, timeout_in_milliseconds=8000):
    # Keep the window alive (so animations and background threads run) until something is true.
    waited = 0

    while waited < timeout_in_milliseconds:
        if condition_function():
            return True

        QTest.qWait(50)
        waited = waited + 50

    return False


def take_screenshot(window, name):
    if SCREENSHOT_FOLDER != "":
        QTest.qWait(450)
        window.grab().save(os.path.join(SCREENSHOT_FOLDER, name + ".png"))


def find_buttons(parent_widget, button_text):
    found = []

    for button in parent_widget.findChildren(widgets.SoftButton):
        if button.text() == button_text:
            found.append(button)

    return found


def click(button):
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


def has_text(parent_widget, wanted_text):
    # Look in ordinary labels, and in the titles of expandable panels (those are painted by hand).
    for label in parent_widget.findChildren(widgets.QLabel):
        if wanted_text in label.text():
            return True

    for header in parent_widget.findChildren(widgets.PanelHeader):
        if wanted_text in header.title_text or wanted_text in header.summary_text:
            return True

    return False


def write_sample_pdf(file_name, lines):
    pdf_path = os.path.join(TEST_WORKSPACE, file_name)

    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(sample_pdf.build_sample_pdf(lines))

    return pdf_path


# Dialogs must never wait for a human during a test, so they are replaced.
chosen_save_path = {"path": ""}
dialog_answer = {"answer": QMessageBox.StandardButton.Yes}


def fake_save_dialog(*arguments, **keyword_arguments):
    return chosen_save_path["path"], ""


def fake_question(*arguments, **keyword_arguments):
    return dialog_answer["answer"]


QFileDialog.getSaveFileName = fake_save_dialog
QMessageBox.question = fake_question
QMessageBox.warning = fake_question

window = MainWindow()
window.resize(1240, 820)
window.show()
QTest.qWait(600)


def run_all_checks():
    # ------------------------------------------------------------------
    print("")
    print("Dashboard")
    check("The window opens on the dashboard", window.current_page_name == "dashboard")
    dashboard = window.pages["dashboard"]
    check("The empty activity list invites the person to act", has_text(dashboard, "Nothing here yet"))
    take_screenshot(window, "01_dashboard_empty")

    sign_card = dashboard.findChildren(widgets.HoverCard)[0]
    QTest.mouseClick(sign_card, Qt.MouseButton.LeftButton)
    check("The 'Sign a PDF' quick action opens the signing page", window.current_page_name == "sign")
    take_screenshot(window, "02_sign_without_identity")

    sign_page = window.pages["sign"]
    check("Signing is disabled while nothing is chosen", not sign_page.sign_button.isEnabled())
    check("The signing page offers to create an identity first", len(find_buttons(sign_page, "Create an identity")) == 1)

    click(find_buttons(sign_page, "Create an identity")[0])
    check("'Create an identity' leads to key generation", window.current_page_name == "keys")

    # ------------------------------------------------------------------
    print("")
    print("Key generation")
    keys_page = window.pages["keys"]
    take_screenshot(window, "03_keys_empty")

    click(keys_page.generate_button)
    check("An empty name is rejected", has_text(keys_page, "Enter a name"))

    keys_page.name_input.setText("Alice Example")
    keys_page.password_input.setText(STRONG_PASSWORD)
    keys_page.password_repeat_input.setText("something different")
    click(keys_page.generate_button)
    check("Two different passwords are rejected", has_text(keys_page, "do not match"))

    keys_page.password_input.setText("short")
    keys_page.password_repeat_input.setText("short")
    click(keys_page.generate_button)
    wait_until(lambda: keys_page.task_thread is not None and keys_page.task_thread.isFinished())
    QTest.qWait(300)
    check("A too-short password is rejected by the backend", has_text(keys_page, "at least 12"))
    check("Nothing was saved after a rejected attempt", len(identity_storage.list_identity_summaries()) == 0)

    keys_page.organization_input.setText("Example Org")
    keys_page.country_input.setText("in")
    keys_page.password_input.setText(STRONG_PASSWORD)
    keys_page.password_repeat_input.setText(STRONG_PASSWORD)
    click(keys_page.generate_button)
    check("Generation shows its progress", keys_page.progress.isVisible())
    take_screenshot(window, "04_keys_progress")
    wait_until(lambda: len(identity_storage.list_identity_summaries()) == 1)
    wait_until(lambda: keys_page.task_thread is None)
    QTest.qWait(500)

    identities = identity_storage.list_identity_summaries()
    check("An identity was created and saved", len(identities) == 1)
    alice = identities[0]
    check("It uses ECDSA on the P-256 curve", alice["certificate"]["curve"] == "P-256 (secp256r1)")
    check("Its private key is encrypted with the password", alice["password_protected"])
    check("The list on the page shows the new identity", len(keys_page.findChildren(widgets.HoverCard)) == 1)
    check("The form was cleared and the button works again", keys_page.generate_button.isEnabled() and keys_page.name_input.text() == "")
    take_screenshot(window, "05_keys_with_identity")

    keys_page.unprotected_checkbox.setChecked(True)
    check("Choosing 'no password' disables the password boxes", not keys_page.password_input.isEnabled())
    keys_page.name_input.setText("Bob Unprotected")
    click(keys_page.generate_button)
    wait_until(lambda: len(identity_storage.list_identity_summaries()) == 2)
    wait_until(lambda: keys_page.task_thread is None)
    QTest.qWait(500)
    check("An unprotected identity needs the explicit tick and then works", len(identity_storage.list_identity_summaries()) == 2)
    keys_page.unprotected_checkbox.setChecked(False)

    # ------------------------------------------------------------------
    print("")
    print("Identity details (card grows into a detailed view)")
    alice_card = keys_page.findChildren(widgets.HoverCard)[0]

    for card in keys_page.findChildren(widgets.HoverCard):
        if card.identity_id == alice["identity_id"]:
            alice_card = card

    QTest.mouseClick(alice_card, Qt.MouseButton.LeftButton)
    check("The detailed view starts at the size of the card", keys_page.detail_view is not None)
    QTest.qWait(150)
    take_screenshot(window, "06_detail_mid_animation")
    wait_until(lambda: keys_page.detail_view.geometry() == keys_page.rect() and keys_page.detail_view.scroll_area.isVisible())
    check("It grows to fill the page", keys_page.detail_view.geometry() == keys_page.rect())
    QTest.qWait(500)
    take_screenshot(window, "07_detail_open")

    detail = keys_page.detail_view
    check("The certificate subject is shown", has_text(detail, "Alice Example"))
    check("The fingerprint is shown", has_text(detail, "Fingerprint"))
    check("The private key warning is shown", has_text(detail, "Never share it"))

    panels = detail.findChildren(widgets.ExpandablePanel)
    validity_panel = panels[1]
    check("Panels start closed (except the first)", not validity_panel.is_expanded and panels[0].is_expanded)
    validity_panel.header.clicked.emit()
    wait_until(lambda: validity_panel.body_container.height() > 40)
    QTest.qWait(300)
    check("A panel opens smoothly when clicked", validity_panel.is_expanded and validity_panel.body_container.height() > 40)
    take_screenshot(window, "08_detail_panel_open")

    export_path = os.path.join(TEST_WORKSPACE, "alice-certificate.pem")
    chosen_save_path["path"] = export_path
    click(find_buttons(detail, "Certificate (.pem)")[0])
    check("The certificate can be exported", os.path.exists(export_path) and b"BEGIN CERTIFICATE" in open(export_path, "rb").read())

    export_path = os.path.join(TEST_WORKSPACE, "alice-public.pem")
    chosen_save_path["path"] = export_path
    click(find_buttons(detail, "Public key (.pem)")[0])
    check("The public key can be exported", os.path.exists(export_path) and b"BEGIN PUBLIC KEY" in open(export_path, "rb").read())

    export_path = os.path.join(TEST_WORKSPACE, "alice-private.pem")
    chosen_save_path["path"] = export_path
    click(find_buttons(detail, "Encrypted private key (.pem)")[0])
    check("The private key is exported only in encrypted form", os.path.exists(export_path) and b"BEGIN ENCRYPTED PRIVATE KEY" in open(export_path, "rb").read())

    dialog_answer["answer"] = QMessageBox.StandardButton.No
    export_path = os.path.join(TEST_WORKSPACE, "refused.pem")
    chosen_save_path["path"] = export_path
    click(find_buttons(detail, "Encrypted private key (.pem)")[0])
    check("Declining the private key warning exports nothing", not os.path.exists(export_path))
    dialog_answer["answer"] = QMessageBox.StandardButton.Yes

    click(find_buttons(detail, "Back to identities")[0])
    wait_until(lambda: keys_page.detail_view is None)
    check("The detailed view shrinks back into the list", keys_page.detail_view is None)

    # Bob has no password, so his private key must not be exportable.
    bob_id = ""

    for summary in identity_storage.list_identity_summaries():
        if summary["common_name"] == "Bob Unprotected":
            bob_id = summary["identity_id"]

    bob_card = alice_card

    for card in keys_page.findChildren(widgets.HoverCard):
        if card.identity_id == bob_id:
            bob_card = card

    QTest.mouseClick(bob_card, Qt.MouseButton.LeftButton)
    wait_until(lambda: keys_page.detail_view is not None and keys_page.detail_view.scroll_area.isVisible())
    QTest.qWait(400)
    check("An unprotected private key cannot be exported (button is off)", not find_buttons(keys_page.detail_view, "Encrypted private key (.pem)")[0].isEnabled())
    check("The detailed view warns about the missing password", has_text(keys_page.detail_view, "without a password"))
    take_screenshot(window, "09_detail_unprotected")

    click(find_buttons(keys_page.detail_view, "Delete identity")[0])
    wait_until(lambda: keys_page.detail_view is None)
    check("An identity can be deleted", not identity_storage.identity_exists(bob_id))
    check("Its private key file is gone", not os.path.exists(identity_storage.build_private_key_path(bob_id)))

    # ------------------------------------------------------------------
    print("")
    print("Signing")
    window.show_page("sign")
    QTest.qWait(400)
    check("The identity is available for signing", sign_page.current_identity_id() == alice["identity_id"])
    check("A password box appears for a protected key", sign_page.password_field.isVisibleTo(sign_page))
    check("The certificate details are shown", has_text(sign_page, "Subject and issuer"))

    not_a_pdf_path = os.path.join(TEST_WORKSPACE, "notes.pdf")
    with open(not_a_pdf_path, "wb") as fake_file:
        fake_file.write(b"This is only text, not a PDF.")

    sign_page.drop_zone.file_chosen.emit(not_a_pdf_path)
    QTest.qWait(300)
    check("A fake PDF is rejected with a clear message", has_text(sign_page, "not a PDF"))
    check("Signing stays disabled for it", not sign_page.sign_button.isEnabled())

    original_path = write_sample_pdf("contract.pdf", ["Payment Agreement", "Pay Alice 100 dollars by Friday."])
    original_bytes = open(original_path, "rb").read()
    sign_page.drop_zone.file_chosen.emit(original_path)
    QTest.qWait(300)
    check("A real PDF is accepted", sign_page.pdf_path == original_path and sign_page.sign_button.isEnabled())
    check("The summary shows the file name", has_text(sign_page, "contract.pdf"))
    check("The summary shows SHA-256", has_text(sign_page, "SHA-256"))
    take_screenshot(window, "10_sign_ready")

    sign_page.reason_input.setText("I approve this contract")
    sign_page.location_input.setText("Pune")
    click(sign_page.sign_button)
    check("Signing without the password is refused", has_text(sign_page, "Enter the password"))

    sign_page.password_input.setText("the wrong password!!")
    click(sign_page.sign_button)
    wait_until(lambda: sign_page.task_thread is None, 8000)
    QTest.qWait(300)
    check("Signing with a wrong password is refused", has_text(sign_page, "password may be wrong"))
    check("The button is usable again afterwards", sign_page.sign_button.isEnabled())

    sign_page.password_input.setText(STRONG_PASSWORD)
    click(sign_page.sign_button)
    check("Signing shows animated progress", sign_page.progress.isVisible())
    QTest.qWait(400)
    take_screenshot(window, "11_sign_progress")
    wait_until(lambda: sign_page.stack.currentIndex() == 1, 10000)
    QTest.qWait(500)
    check("The result view appears", sign_page.stack.currentIndex() == 1)
    take_screenshot(window, "12_sign_result")

    result = sign_page.last_result
    check("The signed file exists in the signed_documents folder", os.path.exists(result["signed_file_path"]))
    signed_bytes = open(result["signed_file_path"], "rb").read()
    check("The original PDF was not touched", open(original_path, "rb").read() == original_bytes)
    check("The signed file keeps every original byte (incremental update)", signed_bytes.startswith(original_bytes))
    check("The signature is ECDSA with SHA-256", result["signature"]["signature_algorithm"] == "ECDSA with SHA-256" and result["signature"]["digest_algorithm"] == "SHA-256")
    check("The signature is a PAdES CMS signature", "PAdES" in result["signature"]["signature_format"])
    check("The result says valid, but never 'trusted' for a self-signed certificate", result["signature"]["verdict"] == "valid_untrusted")

    saved_copy_path = os.path.join(TEST_WORKSPACE, "my_copy.pdf")
    chosen_save_path["path"] = saved_copy_path
    click(find_buttons(sign_page, "Save a copy as...")[0])
    check("The signed PDF can be saved anywhere", os.path.exists(saved_copy_path) and open(saved_copy_path, "rb").read() == signed_bytes)

    # ------------------------------------------------------------------
    print("")
    print("Verifying")
    click(find_buttons(sign_page, "Verify this file")[0])
    check("'Verify this file' opens the verification page", window.current_page_name == "verify")
    verify_page = window.pages["verify"]
    check("Verification shows progress", verify_page.progress.isVisible())
    wait_until(lambda: verify_page.task_thread is None and has_text(verify_page, "Signature is cryptographically valid"), 10000)
    QTest.qWait(600)
    take_screenshot(window, "13_verify_untrusted")

    check("It reports a valid signature", has_text(verify_page, "Signature is cryptographically valid"))
    check("It reports nothing changed after signing", has_text(verify_page, "Not changed since signing"))
    check("It reports the certificate is valid today", has_text(verify_page, "Certificate is valid today"))
    check("It says the certificate is NOT trusted", has_text(verify_page, "Certificate is not trusted"))
    check("The headline says 'valid, signer not trusted'", has_text(verify_page, "Signature valid, signer not trusted"))
    check("It admits revocation was not checked", has_text(verify_page, "Revocation was not checked"))
    check("It explains self-signed certificates", has_text(verify_page, "self-signed"))
    check("The reason typed while signing is shown", has_text(verify_page, "I approve this contract"))
    check("The signing certificate details are shown", has_text(verify_page, "Public key and signature"))

    trust_buttons = find_buttons(verify_page, "Trust this certificate")
    check("A 'Trust this certificate' button is offered", len(trust_buttons) == 1)
    dialog_answer["answer"] = QMessageBox.StandardButton.No
    click(trust_buttons[0])
    QTest.qWait(300)
    check("Declining the confirmation trusts nothing", len(trust_store.load_trusted_certificates()) == 0)
    dialog_answer["answer"] = QMessageBox.StandardButton.Yes

    trust_buttons = find_buttons(verify_page, "Trust this certificate")
    click(trust_buttons[0])
    wait_until(lambda: verify_page.task_thread is None and has_text(verify_page, "Signature valid, signer trusted"), 10000)
    QTest.qWait(600)
    take_screenshot(window, "14_verify_trusted")
    check("After the person chooses to trust it, the headline becomes 'signer trusted'", has_text(verify_page, "Signature valid, signer trusted"))
    check("The trust line now passes", has_text(verify_page, "Certificate chain is trusted"))

    # Tamper with the content of the signed file and verify it again.
    tampered_bytes = signed_bytes.replace(b"Pay Alice 100", b"Pay Alice 900")
    tampered_path = os.path.join(TEST_WORKSPACE, "tampered.pdf")
    with open(tampered_path, "wb") as tampered_file:
        tampered_file.write(tampered_bytes)

    verify_page.drop_zone.file_chosen.emit(tampered_path)
    wait_until(lambda: verify_page.task_thread is None and has_text(verify_page, "Signature is not valid"), 10000)
    QTest.qWait(600)
    take_screenshot(window, "15_verify_tampered")
    check("A tampered document is reported as not valid", has_text(verify_page, "Signature is not valid"))
    check("It is reported as changed after signing", has_text(verify_page, "Changed after signing"))
    check("It is never reported as trusted", not has_text(verify_page, "Certificate chain is trusted"))
    check("No trust button is offered for an invalid signature", len(find_buttons(verify_page, "Trust this certificate")) == 0)

    verify_page.drop_zone.file_chosen.emit(original_path)
    wait_until(lambda: verify_page.task_thread is None and has_text(verify_page, "No signatures found"), 10000)
    QTest.qWait(400)
    check("An unsigned PDF is reported as having no signatures", has_text(verify_page, "No signatures found"))

    verify_page.drop_zone.file_chosen.emit(not_a_pdf_path)
    QTest.qWait(400)
    check("A non-PDF is rejected on the verification page", has_text(verify_page, "not a PDF"))

    # ------------------------------------------------------------------
    print("")
    print("Certificates and dashboard")
    window.show_page("certificates")
    QTest.qWait(500)
    certificates_page = window.pages["certificates"]
    take_screenshot(window, "16_certificates")
    check("Your own certificate is listed", has_text(certificates_page, "Alice Example"))
    remove_buttons = find_buttons(certificates_page, "Remove from trusted list")
    check("The trusted certificate is listed with a remove button", len(remove_buttons) == 1)
    click(remove_buttons[0])
    QTest.qWait(300)
    check("A certificate can be removed from the trusted list", len(trust_store.load_trusted_certificates()) == 0)

    window.show_page("dashboard")
    QTest.qWait(1100)
    dashboard = window.pages["dashboard"]
    take_screenshot(window, "17_dashboard_with_activity")
    check("The dashboard counts the signed document", dashboard.signed_number.text() == "1")
    # Three verifications were recorded: the freshly signed file, the tampered file and the unsigned file.
    # (Re-checking after choosing to trust a certificate is not counted twice, and rejected files are not counted.)
    check("The dashboard counts the verifications", dashboard.verified_number.text() == "3")
    check("The dashboard counts the identities", dashboard.identity_number.text() == "1")
    check("Recent activity lists the signing", has_text(dashboard, "contract.pdf"))

    # Navigation by clicking the sidebar.
    click_target = window.navigation_buttons["verify"]
    QTest.mouseClick(click_target, Qt.MouseButton.LeftButton)
    QTest.qWait(600)
    check("The sidebar switches pages", window.current_page_name == "verify")
    check("The sidebar marker moved to the current item", abs(window.marker.y() - (click_target.y() + 12)) < 30)


try:
    run_all_checks()
finally:
    window.close()
    shutil.rmtree(TEST_WORKSPACE, ignore_errors=True)

print("")
print("Passed: " + str(passed_count) + "   Failed: " + str(failed_count))

if failed_count > 0:
    sys.exit(1)
