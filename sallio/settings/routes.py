"""
settings/routes.py — Business profile & address settings
"""
import os
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sallio.settings import bp
from sallio.models import (
    get_business, update_business_settings,
    add_branch, remove_branch, save_logo
)
from sallio.storage import validate_image, save_file


# ---------------------------------------------------------------------------
# Main Settings Page
# ---------------------------------------------------------------------------

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    business = get_business(current_user.business_id)
    if not business:
        flash('Business not found.', 'error')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        # ── 1. Core profile (bio, phone, head office) ──────────────────────
        if form_type == 'profile':
            bio = request.form.get('bio', '').strip()
            display_phone = request.form.get('display_phone', '').strip()
            head_office = {
                'address': request.form.get('ho_address', '').strip(),
                'city':    request.form.get('ho_city', '').strip(),
                'state':   request.form.get('ho_state', '').strip(),
                'phone':   request.form.get('ho_phone', '').strip(),
            }
            update_business_settings(current_user.business_id, {
                'bio':           bio,
                'display_phone': display_phone,
                'head_office':   head_office,
            })
            flash('Business profile updated.', 'success')

        # ── 2. Add branch (Premium only) ────────────────────────────────────
        elif form_type == 'add_branch':
            if business.get('plan_type') != 'premium':
                flash('Branch offices are a Premium feature.', 'error')
            else:
                branch = {
                    'label':   request.form.get('br_label', '').strip(),
                    'address': request.form.get('br_address', '').strip(),
                    'city':    request.form.get('br_city', '').strip(),
                    'state':   request.form.get('br_state', '').strip(),
                    'phone':   request.form.get('br_phone', '').strip(),
                }
                if not branch['address']:
                    flash('Branch address is required.', 'error')
                elif add_branch(current_user.business_id, branch):
                    flash('Branch office added.', 'success')
                else:
                    flash('Could not add branch. Maximum of 5 branches reached.', 'error')

        return redirect(url_for('settings.index'))

    return render_template('settings/index.html', business=business)


# ---------------------------------------------------------------------------
# Remove Branch
# ---------------------------------------------------------------------------

@bp.route('/branch/remove/<int:index>', methods=['POST'])
@login_required
def remove_branch_route(index):
    business = get_business(current_user.business_id)
    if not business or business.get('plan_type') != 'premium':
        flash('Premium feature only.', 'error')
        return redirect(url_for('settings.index'))

    if remove_branch(current_user.business_id, index):
        flash('Branch removed.', 'success')
    else:
        flash('Could not remove branch.', 'error')

    return redirect(url_for('settings.index'))


# ---------------------------------------------------------------------------
# Logo Upload (Premium only)
# ---------------------------------------------------------------------------

@bp.route('/logo', methods=['POST'])
@login_required
def upload_logo():
    business = get_business(current_user.business_id)
    if not business:
        flash('Business not found.', 'error')
        return redirect(url_for('settings.index'))

    if business.get('plan_type') != 'premium':
        flash('Logo upload is a Premium feature. Upgrade to unlock it.', 'error')
        return redirect(url_for('settings.index'))

    logo_file = request.files.get('logo')
    if not logo_file or not logo_file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('settings.index'))

    # Validate before touching GridFS
    is_valid, error_msg = validate_image(logo_file)
    if not is_valid:
        flash(f'Upload rejected: {error_msg}', 'error')
        return redirect(url_for('settings.index'))

    # Save to GridFS, replacing any previous logo
    old_file_id = business.get('logo_file_id')
    file_id = save_file(logo_file, category='logo', business_id=current_user.business_id)
    save_logo(current_user.business_id, file_id, old_file_id)

    flash('Logo updated successfully.', 'success')
    return redirect(url_for('settings.index'))


# ---------------------------------------------------------------------------
# Remove Logo (Premium only)
# ---------------------------------------------------------------------------

@bp.route('/logo/remove', methods=['POST'])
@login_required
def remove_logo():
    from sallio.storage import delete_file
    from sallio.db import get_db
    from bson.objectid import ObjectId

    business = get_business(current_user.business_id)
    if not business:
        return redirect(url_for('settings.index'))

    old_file_id = business.get('logo_file_id')
    if old_file_id:
        delete_file(old_file_id)
        db = get_db()
        db.businesses.update_one(
            {'_id': ObjectId(current_user.business_id)},
            {'$unset': {'logo_file_id': ''}}
        )
        flash('Logo removed.', 'success')

    return redirect(url_for('settings.index'))


# ---------------------------------------------------------------------------
# Signature Upload
# ---------------------------------------------------------------------------

@bp.route('/signature', methods=['POST'])
@login_required
def upload_signature():
    from sallio.models import save_signature
    business = get_business(current_user.business_id)
    if not business:
        return jsonify({'success': False, 'message': 'Business not found.'}), 404

    signature_file = request.files.get('signature')
    if not signature_file:
        return jsonify({'success': False, 'message': 'No signature provided.'}), 400

    # Validate image (it's generated from canvas as a PNG Blob)
    is_valid, error_msg = validate_image(signature_file)
    if not is_valid:
        return jsonify({'success': False, 'message': error_msg}), 400

    old_file_id = business.get('signature_file_id')
    file_id = save_file(signature_file, category='signature', business_id=current_user.business_id)
    save_signature(current_user.business_id, file_id, old_file_id)

    return jsonify({'success': True, 'message': 'Signature saved successfully.'})


# ---------------------------------------------------------------------------
# Remove Signature
# ---------------------------------------------------------------------------

@bp.route('/signature/remove', methods=['POST'])
@login_required
def remove_signature():
    from sallio.storage import delete_file
    from sallio.db import get_db
    from bson.objectid import ObjectId

    business = get_business(current_user.business_id)
    if not business:
        return redirect(url_for('settings.index'))

    old_file_id = business.get('signature_file_id')
    if old_file_id:
        delete_file(old_file_id)
        db = get_db()
        db.businesses.update_one(
            {'_id': ObjectId(current_user.business_id)},
            {'$unset': {'signature_file_id': ''}}
        )
        flash('Signature removed.', 'success')

    return redirect(url_for('settings.index'))
