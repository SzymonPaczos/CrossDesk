"""Wykonanie zlecenia przegladarkowego, z zajeciem wiadomosci na wejsciu."""


class BrowserJobService:
    def execute_capture(self, message_id, proposal_id):
        if not self._ledger.claim(message_id, "execute_capture"):
            return
        try:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                raise ProposalNotFoundError(proposal_id)
            running = proposal.transition("RUNNING")
            self._proposals.save(running)
        except BaseException:
            self._ledger.release(message_id)
            raise
        try:
            self._capture(running)
        except Exception as exc:
            self._fail(running, reason=str(exc), message_id=message_id)

    def _fail(self, proposal, reason, message_id):
        self._proposals.save(proposal.failed(reason))
        self._ledger.release(message_id)
