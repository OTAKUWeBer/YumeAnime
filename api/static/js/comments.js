/**
 * comments.js — Episode comment system controller
 * Tenor v1 API key: LIVDSRZULELA
 */
'use strict';

const TENOR_API_KEY = 'LIVDSRZULELA';

class CommentsManager {
    constructor(config) {
        this.animeId = config.animeId;
        this.episodeNum = config.episodeNumber;
        this.isLoggedIn = config.isLoggedIn;
        this.username = config.username || '';
        this.avatar = config.avatar || '';
        this.userId = config.userId || '';

        // GIF picker context: which form triggered it
        this._gifContext = null;    // 'main' | 'reply:<commentId>'
        this._gifUrl = { main: null };  // key -> selected gif url

        this._gifSearchTimeout = null;

        this.DOM = {};
        this._init();
    }

    // ─────────────────────────────────────────────────────────────────
    //  Bootstrap
    // ─────────────────────────────────────────────────────────────────

    _init() {
        this._bindDOM();
        this._bindEpisodeReactions();
        this._bindMainCommentForm();
        this._bindGifPicker();
        this._loadEpisodeReaction();
        this._loadEpisodeReaction();
        this._loadComments();

        // Close all dropdowns when clicking outside
        document.addEventListener('click', () => {
            document.querySelectorAll('.comment-dropdown').forEach(d => d.classList.remove('open'));
        });
    }

    _bindDOM() {
        const $ = id => document.getElementById(id);
        this.DOM = {
            // Episode reaction
            epLikeBtn: $('ep-like-btn'),
            epDislikeBtn: $('ep-dislike-btn'),
            epLikeCount: $('ep-like-count'),
            epDislikeCount: $('ep-dislike-count'),

            // Comment form
            commentForm: $('comment-form'),
            mainTextarea: $('main-comment-textarea'),
            mainGifBtn: $('main-gif-btn'),
            mainGifPreview: $('main-gif-preview'),
            mainGifImg: $('main-gif-img'),
            mainGifRemove: $('main-gif-remove'),
            mainSubmitBtn: $('main-submit-btn'),
            commentTotalEl: $('comment-total'),

            // List
            commentList: $('comment-list'),

            // GIF picker
            gifOverlay: $('gif-picker-overlay'),
            gifSearchInput: $('gif-search-input'),
            gifGrid: $('gif-grid'),
            gifLoading: $('gif-loading'),
            gifCloseBtn: $('gif-close-btn'),
        };
    }

    // ─────────────────────────────────────────────────────────────────
    //  Episode reactions
    // ─────────────────────────────────────────────────────────────────

    _bindEpisodeReactions() {
        if (!this.DOM.epLikeBtn) return;
        this.DOM.epLikeBtn.addEventListener('click', () => this._reactToEpisode('like'));
        this.DOM.epDislikeBtn.addEventListener('click', () => this._reactToEpisode('dislike'));
    }

    async _loadEpisodeReaction() {
        try {
            const r = await fetch(`/api/episodes/reaction?anime_id=${encodeURIComponent(this.animeId)}&ep=${this.episodeNum}`);
            if (!r.ok) return;
            const d = await r.json();
            this._updateEpisodeReactionUI(d);
        } catch (_) { }
    }

    async _reactToEpisode(type) {
        if (!this.isLoggedIn) { openLoginModal && openLoginModal(); return; }
        try {
            const r = await fetch('/api/episodes/reaction', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ anime_id: this.animeId, episode_number: this.episodeNum, type }),
            });
            if (!r.ok) return;
            const d = await r.json();
            this._updateEpisodeReactionUI(d);
        } catch (_) { }
    }

    _updateEpisodeReactionUI(data) {
        if (!this.DOM.epLikeCount) return;
        this._animateCount(this.DOM.epLikeCount, data.like_count ?? 0);
        this._animateCount(this.DOM.epDislikeCount, data.dislike_count ?? 0);
        this.DOM.epLikeBtn.classList.toggle('liked', !!data.user_liked);
        this.DOM.epDislikeBtn.classList.toggle('disliked', !!data.user_disliked);
    }

    // ─────────────────────────────────────────────────────────────────
    //  Comment list
    // ─────────────────────────────────────────────────────────────────

    async _loadComments() {
        const list = this.DOM.commentList;
        if (!list) return;
        list.innerHTML = `<div class="comment-list-loading"><div class="comment-spinner"></div><span>Loading comments…</span></div>`;
        try {
            const r = await fetch(`/api/comments?anime_id=${encodeURIComponent(this.animeId)}&ep=${this.episodeNum}`);
            if (!r.ok) throw new Error('fetch failed');
            const d = await r.json();
            this._renderComments(d.comments || []);
        } catch (_) {
            list.innerHTML = `<div class="comment-list-empty">Failed to load comments. Please try again later.</div>`;
        }
    }

    _renderComments(comments) {
        const list = this.DOM.commentList;
        if (this.DOM.commentTotalEl) this.DOM.commentTotalEl.textContent = comments.length;
        if (!comments.length) {
            list.innerHTML = `<div class="comment-list-empty">No comments yet. Be the first to share your thoughts!</div>`;
            return;
        }
        list.innerHTML = '';
        comments.forEach(c => list.appendChild(this._buildCommentEl(c, false)));
    }

    _buildCommentEl(comment, isReply) {
        const wrapper = document.createElement('div');
        wrapper.className = isReply ? 'reply-item' : 'comment-item';
        wrapper.dataset.commentId = comment._id;

        const userLiked = comment.likes?.includes(this.userId);
        const userDisliked = comment.dislikes?.includes(this.userId);

        const avatarHTML = comment.avatar
            ? `<img class="comment-avatar" src="${this._esc(comment.avatar)}" alt="${this._esc(comment.author)}" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(comment.author)}&size=72&background=1a1a1a&color=fff&bold=true'">`
            : `<div class="comment-avatar-placeholder">${this._esc(comment.author.charAt(0).toUpperCase())}</div>`;

        const gifHTML = comment.gif_url
            ? `<img class="comment-gif" src="${this._esc(comment.gif_url)}" alt="GIF" loading="lazy">`
            : '';

        const repliesHTML = (!isReply && comment.replies?.length)
            ? comment.replies.map(r => this._buildCommentEl(r, true).outerHTML).join('')
            : '';
        const repliesWrapperHTML = repliesHTML
            ? `<div class="comment-replies">${repliesHTML}</div>`
            : (isReply ? '' : `<div class="comment-replies" id="replies-${comment._id}"></div>`);

        const replyBtnHTML = isReply ? '' : `
            <button class="comment-reply-toggle" data-comment-id="${comment._id}">Reply</button>`;

        const isOwner = !comment.deleted && this.isLoggedIn && (
            (comment.author_id && String(comment.author_id) === String(this.userId)) ||
            (!comment.author_id && comment.author === this.username && comment.author !== 'Anonymous')
        );

        const timeDiff = comment.created_at ? (Date.now() - new Date(comment.created_at).getTime()) : Number.MAX_SAFE_INTEGER;
        const canEdit = isOwner && (timeDiff <= 5 * 60 * 1000);

        let menuHTML = '';
        if (isOwner) {
            menuHTML = `
                <div class="comment-menu-container">
                    <button class="comment-menu-btn" data-menu-toggle="${comment._id}" title="Options">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>
                    </button>
                    <div class="comment-dropdown" id="menu-${comment._id}">
                        ${canEdit ? `<button class="comment-dropdown-item" data-action="edit" data-comment-id="${comment._id}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit</button>` : ''}
                        <button class="comment-dropdown-item delete" data-action="delete" data-comment-id="${comment._id}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg> Delete</button>
                    </div>
                </div>
            `;
        }

        wrapper.innerHTML = `
            <div class="comment-header">
                ${avatarHTML}
                <span class="comment-author">${this._esc(comment.author)}</span>
                <span class="comment-time" title="${this._absoluteTime(comment.created_at)}">
                    ${this._relativeTime(comment.created_at)}
                    ${comment.edited_at ? `<span title="Edited at ${this._absoluteTime(comment.edited_at)}"> (edited)</span>` : ''}
                </span>
                ${menuHTML}
            </div>
            ${comment.deleted ? `<p class="comment-body" style="color:var(--text-muted);font-style:italic;">[This comment was deleted]</p>` : (comment.body ? `<p class="comment-body">${this._esc(comment.body)}</p>` : '')}
            ${comment.deleted ? '' : gifHTML}
            <div class="comment-footer">
                <button class="comment-react-btn ${userLiked ? 'liked' : ''}" data-react="like" data-comment-id="${comment._id}" title="Like">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="${userLiked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                    <span class="comment-like-count">${comment.like_count ?? 0}</span>
                </button>
                <button class="comment-react-btn ${userDisliked ? 'disliked' : ''}" data-react="dislike" data-comment-id="${comment._id}" title="Dislike">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="${userDisliked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
                    <span class="comment-dislike-count">${comment.dislike_count ?? 0}</span>
                </button>
                ${replyBtnHTML}
            </div>
            ${!isReply ? `<div class="reply-form-container" id="reply-form-${comment._id}" style="display:none;"></div>` : ''}
            ${repliesWrapperHTML}
        `;

        // Bind reactions
        wrapper.querySelectorAll('[data-react]').forEach(btn => {
            btn.addEventListener('click', () => this._reactToComment(comment._id, btn.dataset.react, btn));
        });

        // Bind reply toggle
        const replyToggle = wrapper.querySelector('.comment-reply-toggle');
        if (replyToggle) {
            replyToggle.addEventListener('click', () => this._toggleReplyForm(comment._id, wrapper));
        }

        // Bind Edit/Delete
        if (isOwner) {
            const toggleBtn = wrapper.querySelector(`[data-menu-toggle="${comment._id}"]`);
            const menuDropdown = wrapper.querySelector(`#menu-${comment._id}`);
            if (toggleBtn && menuDropdown) {
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const wasOpen = menuDropdown.classList.contains('open');
                    document.querySelectorAll('.comment-dropdown').forEach(d => d.classList.remove('open'));
                    if (!wasOpen) menuDropdown.classList.add('open');
                });
            }

            const editBtn = wrapper.querySelector(`[data-action="edit"][data-comment-id="${comment._id}"]`);
            if (editBtn) editBtn.addEventListener('click', () => this._startEditComment(comment, wrapper));

            const deleteBtn = wrapper.querySelector(`[data-action="delete"][data-comment-id="${comment._id}"]`);
            if (deleteBtn) deleteBtn.addEventListener('click', () => this._deleteComment(comment._id, wrapper));
        }

        return wrapper;
    }

    // ─────────────────────────────────────────────────────────────────
    //  Comment reactions
    // ─────────────────────────────────────────────────────────────────

    async _reactToComment(commentId, type, btn) {
        if (!this.isLoggedIn) { openLoginModal && openLoginModal(); return; }
        try {
            const r = await fetch(`/api/comments/${commentId}/react`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type }),
            });
            if (!r.ok) return;
            const d = await r.json();

            // Find the comment footer directly
            const footer = btn.closest('.comment-footer');
            if (!footer) return;

            const likeBtn = footer.querySelector('[data-react="like"]');
            const dislikeBtn = footer.querySelector('[data-react="dislike"]');
            if (!likeBtn || !dislikeBtn) return;

            likeBtn.classList.toggle('liked', d.user_liked);
            dislikeBtn.classList.toggle('disliked', d.user_disliked);

            // Update SVG fill for visual feedback
            likeBtn.querySelector('svg').setAttribute('fill', d.user_liked ? 'currentColor' : 'none');
            dislikeBtn.querySelector('svg').setAttribute('fill', d.user_disliked ? 'currentColor' : 'none');

            this._animateCount(likeBtn.querySelector('.comment-like-count'), d.like_count);
            this._animateCount(dislikeBtn.querySelector('.comment-dislike-count'), d.dislike_count);
        } catch (_) { }
    }

    // ─────────────────────────────────────────────────────────────────
    //  Main comment form
    // ─────────────────────────────────────────────────────────────────

    _bindMainCommentForm() {
        if (!this.DOM.mainSubmitBtn) return;
        this.DOM.mainSubmitBtn.addEventListener('click', () => this._submitComment());
        this.DOM.mainTextarea?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._submitComment();
            }
        });
        this.DOM.mainGifBtn?.addEventListener('click', (e) => {
            this._gifContext = 'main';
            this._openGifPicker(e.currentTarget);
        });
        this.DOM.mainGifRemove?.addEventListener('click', () => {
            this._gifUrl.main = null;
            this.DOM.mainGifPreview.style.display = 'none';
            this.DOM.mainGifImg.src = '';
        });
    }

    async _submitComment() {
        if (!this.isLoggedIn) { openLoginModal && openLoginModal(); return; }
        const body = this.DOM.mainTextarea?.value.trim() || '';
        const gifUrl = this._gifUrl.main || null;
        if (!body && !gifUrl) return;

        this.DOM.mainSubmitBtn.disabled = true;
        this.DOM.mainSubmitBtn.innerHTML = `<div class="comment-spinner" style="width:16px;height:16px;border-width:2px;border-top-color:#fff;"></div>`;

        try {
            const r = await fetch('/api/comments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    anime_id: this.animeId,
                    episode_number: this.episodeNum,
                    body,
                    gif_url: gifUrl,
                }),
            });
            const d = await r.json();
            if (!r.ok) {
                this._showToast(d.message || 'Failed to post.', 'error');
                return;
            }
            // Reset form
            if (this.DOM.mainTextarea) this.DOM.mainTextarea.value = '';
            this._gifUrl.main = null;
            if (this.DOM.mainGifPreview) this.DOM.mainGifPreview.style.display = 'none';
            if (this.DOM.mainGifImg) this.DOM.mainGifImg.src = '';

            // Prepend new comment
            const el = this._buildCommentEl(d.comment, false);
            const list = this.DOM.commentList;
            const empty = list.querySelector('.comment-list-empty');
            if (empty) empty.remove();
            list.insertBefore(el, list.firstChild);

            // Update count
            const cur = parseInt(this.DOM.commentTotalEl?.textContent || '0');
            if (this.DOM.commentTotalEl) this.DOM.commentTotalEl.textContent = cur + 1;

            this._showToast('Comment posted!', 'success');
        } catch (_) {
            this._showToast('Network error. Please try again.', 'error');
        } finally {
            this.DOM.mainSubmitBtn.disabled = false;
            this.DOM.mainSubmitBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg><span>Post</span>`;
        }
    }

    // ─────────────────────────────────────────────────────────────────
    //  Reply form
    // ─────────────────────────────────────────────────────────────────

    _toggleReplyForm(commentId, commentWrapper) {
        const container = commentWrapper.querySelector(`#reply-form-${commentId}`);
        if (!container) return;

        if (container.style.display !== 'none') {
            container.style.display = 'none';
            container.innerHTML = '';
            return;
        }
        if (!this.isLoggedIn) { openLoginModal && openLoginModal(); return; }

        const replyKey = `reply:${commentId}`;
        this._gifUrl[replyKey] = null;

        container.style.display = 'block';
        container.innerHTML = `
            <div class="reply-form-wrapper">
                <div class="comment-input-row">
                    ${this.avatar
                ? `<img class="comment-avatar" src="${this._esc(this.avatar)}" alt="${this._esc(this.username)}" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(this.username)}&size=72&background=1a1a1a&color=fff&bold=true'">`
                : `<div class="comment-avatar-placeholder">${this._esc(this.username.charAt(0).toUpperCase())}</div>`
            }
                    <div class="comment-input-wrapper">
                        <textarea class="comment-textarea reply-textarea" placeholder="Write a reply… (Enter to post)" id="reply-textarea-${commentId}"></textarea>
                        <div class="reply-gif-preview" id="reply-gif-preview-${commentId}" style="display:none;">
                            <div class="comment-gif-preview">
                                <img id="reply-gif-img-${commentId}" src="" alt="GIF">
                                <button class="comment-gif-remove" id="reply-gif-remove-${commentId}" title="Remove GIF">✕</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="reply-form-actions">
                    <button type="button" class="comment-gif-btn" id="reply-gif-btn-${commentId}" title="Add GIF">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                        <span>GIF</span>
                    </button>
                    <button class="reply-cancel-btn" id="reply-cancel-${commentId}">Cancel</button>
                    <button class="comment-submit-btn" id="reply-submit-${commentId}" title="Post reply">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                        <span>Reply</span>
                    </button>
                </div>
            </div>
        `;

        const textarea = container.querySelector(`#reply-textarea-${commentId}`);
        const submitBtn = container.querySelector(`#reply-submit-${commentId}`);
        const cancelBtn = container.querySelector(`#reply-cancel-${commentId}`);
        const gifBtn = container.querySelector(`#reply-gif-btn-${commentId}`);
        const gifPreview = container.querySelector(`#reply-gif-preview-${commentId}`);
        const gifImg = container.querySelector(`#reply-gif-img-${commentId}`);
        const gifRemove = container.querySelector(`#reply-gif-remove-${commentId}`);

        textarea?.focus();

        gifBtn?.addEventListener('click', (e) => {
            this._gifContext = replyKey;
            this._openGifPicker(e.currentTarget);
        });

        gifRemove?.addEventListener('click', () => {
            this._gifUrl[replyKey] = null;
            if (gifPreview) gifPreview.style.display = 'none';
            if (gifImg) gifImg.src = '';
        });

        cancelBtn?.addEventListener('click', () => {
            container.style.display = 'none';
            container.innerHTML = '';
            delete this._gifUrl[replyKey];
        });

        const doSubmit = async () => {
            const body = textarea?.value.trim() || '';
            const gifUrl = this._gifUrl[replyKey] || null;
            if (!body && !gifUrl) return;

            submitBtn.disabled = true;
            submitBtn.innerHTML = `<div class="comment-spinner" style="width:16px;height:16px;border-width:2px;border-top-color:#fff;"></div>`;

            try {
                const r = await fetch(`/api/comments/${commentId}/reply`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        anime_id: this.animeId,
                        episode_number: this.episodeNum,
                        body,
                        gif_url: gifUrl,
                    }),
                });
                const d = await r.json();
                if (!r.ok) { this._showToast(d.message || 'Failed to post.', 'error'); return; }

                // Insert reply into the thread
                const repliesContainer = commentWrapper.querySelector(`#replies-${commentId}`)
                    || commentWrapper.querySelector('.comment-replies');
                if (repliesContainer) {
                    const replyEl = this._buildCommentEl(d.comment, true);
                    repliesContainer.appendChild(replyEl);
                }

                // Close form
                container.style.display = 'none';
                container.innerHTML = '';
                delete this._gifUrl[replyKey];

                this._showToast('Reply posted!', 'success');
            } catch (_) {
                this._showToast('Network error.', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg><span>Reply</span>`;
                }
            }
        };

        submitBtn?.addEventListener('click', doSubmit);
        textarea?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                doSubmit();
            }
        });

        // Expose gif preview helpers to selectGif()
        container._gifPreview = gifPreview;
        container._gifImg = gifImg;
    }

    // ─────────────────────────────────────────────────────────────────
    //  Edit / Delete
    // ─────────────────────────────────────────────────────────────────

    async _deleteComment(commentId, wrapper) {
        if (!confirm('Are you sure you want to delete this comment?')) return;

        try {
            const r = await fetch(`/api/comments/${commentId}`, { method: 'DELETE' });
            if (!r.ok) {
                const d = await r.json();
                this._showToast(d.message || 'Failed to delete.', 'error');
                return;
            }

            // Re-fetch comments to cleanly re-render soft vs hard deleted threads
            this._loadComments();
            this._showToast('Comment deleted', 'success');
        } catch (_) {
            this._showToast('Network error.', 'error');
        }
    }

    _startEditComment(comment, wrapper) {
        wrapper.classList.add('is-editing');
        const editKey = `edit:${comment._id}`;
        this._gifUrl[editKey] = comment.gif_url || null;

        const container = document.createElement('div');
        container.className = 'comment-edit-form';
        container.innerHTML = `
            <div class="comment-input-row">
                <div class="comment-input-wrapper">
                    <textarea class="comment-textarea edit-textarea" id="edit-textarea-${comment._id}" placeholder="Edit your comment… (Enter to save)">${this._esc(comment.body)}</textarea>
                    <div class="reply-gif-preview" id="edit-gif-preview-${comment._id}" style="${comment.gif_url ? 'display:block;' : 'display:none;'}">
                        <div class="comment-gif-preview">
                            <img id="edit-gif-img-${comment._id}" src="${this._esc(comment.gif_url)}" alt="GIF">
                            <button class="comment-gif-remove" id="edit-gif-remove-${comment._id}" title="Remove GIF">✕</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="reply-form-actions">
                <button type="button" class="comment-gif-btn" id="edit-gif-btn-${comment._id}" title="Add GIF">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                    <span>GIF</span>
                </button>
                <button class="reply-cancel-btn" id="edit-cancel-${comment._id}">Cancel</button>
                <button class="comment-submit-btn" id="edit-submit-${comment._id}" title="Save edit" style="width:auto; border-radius:var(--radius-sm); padding:6px 16px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    <span style="display:inline;">Save</span>
                </button>
            </div>
        `;

        wrapper.appendChild(container);

        const textarea = container.querySelector(`#edit-textarea-${comment._id}`);
        const submitBtn = container.querySelector(`#edit-submit-${comment._id}`);
        const cancelBtn = container.querySelector(`#edit-cancel-${comment._id}`);
        const gifBtn = container.querySelector(`#edit-gif-btn-${comment._id}`);
        const gifPreview = container.querySelector(`#edit-gif-preview-${comment._id}`);
        const gifImg = container.querySelector(`#edit-gif-img-${comment._id}`);
        const gifRemove = container.querySelector(`#edit-gif-remove-${comment._id}`);

        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);

        const closeEdit = () => {
            wrapper.classList.remove('is-editing');
            container.remove();
            delete this._gifUrl[editKey];
        };

        cancelBtn.addEventListener('click', closeEdit);

        gifBtn.addEventListener('click', (e) => {
            this._gifContext = editKey;
            this._openGifPicker(e.currentTarget);
        });

        gifRemove.addEventListener('click', () => {
            this._gifUrl[editKey] = null;
            gifPreview.style.display = 'none';
            gifImg.src = '';
        });

        const doSave = async () => {
            const body = textarea.value.trim();
            const gifUrl = this._gifUrl[editKey] || null;
            if (!body && !gifUrl) return;

            submitBtn.disabled = true;
            submitBtn.innerHTML = `<div class="comment-spinner" style="width:16px;height:16px;border-width:2px;border-top-color:#fff;"></div>`;

            try {
                const r = await fetch(`/api/comments/${comment._id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ body, gif_url: gifUrl }),
                });
                const d = await r.json();
                if (!r.ok) {
                    this._showToast(d.message || 'Failed to edit.', 'error');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span style="display:inline;">Save</span>`;
                    return;
                }

                closeEdit();
                // Replace the entire wrapper with updated block (preserves existing replies logic)
                const isReply = wrapper.classList.contains('reply-item');
                // Persist existing replies visually without refetching recursively
                const existingRepliesHTML = wrapper.querySelector('.comment-replies')?.innerHTML || '';

                const newEl = this._buildCommentEl(d.comment, isReply);
                if (!isReply) {
                    const repliesContainer = newEl.querySelector('.comment-replies');
                    if (repliesContainer) repliesContainer.innerHTML = existingRepliesHTML;
                }

                wrapper.replaceWith(newEl);
                this._showToast('Comment updated!', 'success');
            } catch (_) {
                this._showToast('Network error.', 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span style="display:inline;">Save</span>`;
            }
        };

        submitBtn.addEventListener('click', doSave);
        textarea.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSave(); }
        });

        container._gifPreview = gifPreview;
        container._gifImg = gifImg;
    }

    // ─────────────────────────────────────────────────────────────────
    //  GIF Picker
    // ─────────────────────────────────────────────────────────────────

    _bindGifPicker() {
        if (!this.DOM.gifOverlay) return;

        this.DOM.gifCloseBtn?.addEventListener('click', () => this._closeGifPicker());
        this.DOM.gifOverlay.addEventListener('click', e => {
            if (e.target === this.DOM.gifOverlay) this._closeGifPicker();
        });

        this.DOM.gifSearchInput?.addEventListener('input', e => {
            clearTimeout(this._gifSearchTimeout);
            const q = e.target.value.trim();
            this._gifSearchTimeout = setTimeout(() => {
                if (q) this.fetchGifs('search', q);
                else this.fetchGifs('trending');
            }, 400);
        });
    }

    _openGifPicker(btnEl) {
        if (!this.DOM.gifOverlay) return;
        this.DOM.gifOverlay.classList.add('open');
        if (this.DOM.gifSearchInput) this.DOM.gifSearchInput.value = '';
        this.fetchGifs('trending');
        setTimeout(() => this.DOM.gifSearchInput?.focus(), 150);

        if (btnEl) {
            const rect = btnEl.getBoundingClientRect();
            const panel = this.DOM.gifOverlay.querySelector('.gif-picker-panel');

            // Wait for display block to register size
            requestAnimationFrame(() => {
                const pWidth = 320; // Hardcoded from our CSS
                const pHeight = 400;

                // Position above and right-aligned with the button usually
                let top = rect.top - pHeight - 10;
                let left = rect.right - pWidth;

                // Adjust if off-screen top
                if (top < 10) {
                    top = rect.bottom + 10;
                    panel.style.transformOrigin = 'top right';
                } else {
                    panel.style.transformOrigin = 'bottom right';
                }

                // Adjust if off-screen left
                if (left < 10) {
                    left = 10;
                }

                panel.style.top = `${top}px`;
                panel.style.left = `${left}px`;
            });
        }
    }

    _closeGifPicker() {
        this.DOM.gifOverlay?.classList.remove('open');
    }

    async fetchGifs(type = 'trending', query = '') {
        if (!this.DOM.gifGrid || !this.DOM.gifLoading) return;
        this.DOM.gifGrid.innerHTML = '';
        this.DOM.gifLoading.style.display = 'flex';

        let url = `https://g.tenor.com/v1/trending?key=${TENOR_API_KEY}&limit=20&media_filter=minimal`;
        if (type === 'search' && query) {
            url = `https://g.tenor.com/v1/search?key=${TENOR_API_KEY}&q=${encodeURIComponent(query)}&limit=20&media_filter=minimal`;
        }

        try {
            const r = await fetch(url);
            const data = await r.json();
            this.DOM.gifLoading.style.display = 'none';

            if (data.results) {
                data.results.forEach(gif => {
                    const tinygif = gif.media[0]?.tinygif?.url;
                    const fullGif = gif.media[0]?.gif?.url;
                    if (!tinygif || !fullGif) return;

                    const img = document.createElement('img');
                    img.src = tinygif;
                    img.className = 'gif-result-item';
                    img.loading = 'lazy';
                    img.title = gif.title || 'GIF';
                    img.addEventListener('click', () => this.selectGif(fullGif));
                    this.DOM.gifGrid.appendChild(img);
                });

                if (!data.results.length) {
                    this.DOM.gifGrid.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem;padding:12px;grid-column:1/-1;text-align:center">No GIFs found.</p>`;
                }
            }
        } catch (e) {
            console.error('[Tenor] error:', e);
            this.DOM.gifLoading.style.display = 'none';
            this.DOM.gifGrid.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem;padding:12px;grid-column:1/-1;text-align:center">Failed to load GIFs.</p>`;
        }
    }

    selectGif(fullUrl) {
        this._gifUrl[this._gifContext] = fullUrl;

        if (this._gifContext === 'main') {
            if (this.DOM.mainGifImg) this.DOM.mainGifImg.src = fullUrl;
            if (this.DOM.mainGifPreview) this.DOM.mainGifPreview.style.display = 'block';
        } else if (this._gifContext.startsWith('reply:')) {
            // reply context: e.g. 'reply:63abc...'
            const commentId = this._gifContext.replace('reply:', '');
            const container = document.getElementById(`reply-form-${commentId}`);
            if (container) {
                const gifPreview = container.querySelector(`#reply-gif-preview-${commentId}`);
                const gifImg = container.querySelector(`#reply-gif-img-${commentId}`);
                if (gifImg) gifImg.src = fullUrl;
                if (gifPreview) gifPreview.style.display = 'block';
            }
        } else if (this._gifContext.startsWith('edit:')) {
            // edit context
            const commentId = this._gifContext.replace('edit:', '');
            const wrapper = document.querySelector(`[data-comment-id="${commentId}"]`);
            if (wrapper) {
                const container = wrapper.querySelector('.comment-edit-form');
                if (container) {
                    const gifPreview = container.querySelector(`#edit-gif-preview-${commentId}`);
                    const gifImg = container.querySelector(`#edit-gif-img-${commentId}`);
                    if (gifImg) gifImg.src = fullUrl;
                    if (gifPreview) gifPreview.style.display = 'block';
                }
            }
        }

        this._closeGifPicker();
    }

    // ─────────────────────────────────────────────────────────────────
    //  Utilities
    // ─────────────────────────────────────────────────────────────────

    _relativeTime(isoStr) {
        if (!isoStr) return '';
        const diff = Date.now() - new Date(isoStr).getTime();
        const s = Math.floor(diff / 1000);
        if (s < 60) return 'just now';
        const m = Math.floor(s / 60);
        if (m < 60) return `${m}m ago`;
        const h = Math.floor(m / 60);
        if (h < 24) return `${h}h ago`;
        const days = Math.floor(h / 24);
        if (days < 30) return `${days}d ago`;
        const months = Math.floor(days / 30);
        if (months < 12) return `${months}mo ago`;
        return `${Math.floor(months / 12)}y ago`;
    }

    _absoluteTime(isoStr) {
        if (!isoStr) return '';
        try {
            return new Date(isoStr).toLocaleString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            });
        } catch (e) {
            return '';
        }
    }

    _esc(str) {
        return String(str ?? '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    _animateCount(el, value) {
        if (!el) return;
        el.textContent = value;
        el.classList.remove('count-pulse');
        void el.offsetWidth; // reflow
        el.classList.add('count-pulse');
    }

    _showToast(msg, type = 'info') {
        // reuse existing showToast from watch.js if available, else fallback
        if (typeof showToast === 'function') { showToast(msg, type === 'error' ? 'error' : 'success'); return; }
        const container = document.getElementById('toastContainer');
        if (!container) return;
        const toast = document.createElement('div');
        toast.style.cssText = `background:${type === 'error' ? '#ef4444' : 'var(--primary)'};color:#fff;padding:10px 16px;border-radius:8px;font-size:.88rem;font-weight:600;pointer-events:auto;box-shadow:0 4px 15px rgba(0,0,0,.4);animation:commentFadeIn .2s ease;`;
        toast.textContent = msg;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}

// ─────────────────────────────────────────────────────────────────
//  Bootstrap on DOM ready
// ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const cfg = window.COMMENTS_CONFIG;
    if (!cfg) return;
    window._commentsManager = new CommentsManager(cfg);
});
